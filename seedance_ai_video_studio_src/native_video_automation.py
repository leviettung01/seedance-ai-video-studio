"""Native Pro generation with optional installed 30-second Dola skill."""
import asyncio
import json
import re
import time
from urllib.parse import urlsplit


def returned_video_urls(data):
    """Read real media assets, not tool IDs or an assistant's success claim."""
    urls = []
    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            if value.startswith(('https://', 'http://')):
                parsed = urlsplit(value)
                if (re.fullmatch(r'v\d+-dola\.dola\.com', parsed.hostname or '')
                        and '/video/' in parsed.path):
                    urls.append(value)
                elif ((parsed.hostname or '').startswith('vod-urls-')
                      and (parsed.hostname or '').endswith('.byteintlapi.com')
                      and parsed.path.startswith('/video/fplay/')):
                    urls.append(value)
            elif value.lstrip().startswith(('{', '[')):
                try:
                    visit(json.loads(value))
                except ValueError:
                    pass
    visit(data)
    return list(dict.fromkeys(urls))


async def read_chat_video_assets(page):
    # Dola can finish a task in its persisted conversation while the original
    # streaming tab stays on "generating" without mounting a <video> element.
    if not re.search(r'/chat/\d+', page.url):
        return []
    check = await page.context.new_page()
    try:
        async with check.expect_response(lambda r: '/im/chain/single' in r.url and r.status == 200, timeout=15000) as response:
            await check.goto(page.url, wait_until='domcontentloaded', timeout=20000)
        return returned_video_urls(await (await response.value).json())
    finally:
        await check.close()


def stream_error(text):
    """Read business errors even when the HTTP response is 200/SSE."""
    try:
        data = json.loads(text)
        code = data.get('error_code', data.get('code', 0))
        if code not in (0, '0', None):
            return f"Dola {code}: {data.get('error_msg') or data.get('msg') or data.get('message', '')}"
    except (ValueError, AttributeError):
        pass
    for line in text.splitlines():
        if not line.startswith('data:'):
            continue
        try:
            data = json.loads(line[5:].strip())
            if data.get('error_code'):
                return ('Dola 710022002: Quá nhiều yêu cầu; tài khoản hoặc IP đang bị giới hạn, chưa xác nhận tạo video.'
                        if str(data['error_code']) == '710022002' else
                        f"Dola {data['error_code']}: {data.get('error_msg', '')}")
        except (ValueError, AttributeError):
            continue
    return ''


def failure_message(assistant_text, failed_cards=0):
    if failed_cards:
        return 'Dola hiển thị thẻ Không thể tạo video; chưa tạo được video.'
    text = assistant_text.lower()
    for marker in ('task_id rỗng', 'task id is empty', 'insufficient credits',
                   'hết credit', 'không có đủ điểm', 'không thể tạo video',
                   'không hỗ trợ 15', 'không hỗ trợ 30', 'does not support 30', 'chỉ hỗ trợ 5 hoặc 10', 'common invalid param'):
        if marker in text:
            return assistant_text[-1200:]
    for marker in ('insufficient credit', 'not enough credits', 'daily limit reached',
                   'unable to generate video', 'cannot generate video', 'video generation failed',
                   'generation limit reached', 'content generation for this request is prohibited',
                   'retries are not permitted'):
        if marker in text:
            return assistant_text[-1200:]
    return ''


async def verify_skill_token(editor):
    """Confirm the active native Skill chip survived chat activation."""
    from dola_skill_automation import SKILL_LABEL
    for _ in range(20):
        if SKILL_LABEL.search((await editor.inner_text()).strip()):
            return
        await asyncio.sleep(0.5)
    raise RuntimeError('SKILL_ACTIVATION_FAILED: chat Pro chưa giữ token Skill trong ô nhập.')


class NativeVideoAutomation:
    """A server acknowledgement is progress, never a completed local video."""
    def __init__(self):
        self._cancel_flag = False
        self.last_chat_url = ''
        self.last_prompt_number = 0

    def cancel(self):
        self._cancel_flag = True

    async def execute_generation_flow(self, page, prompt, aspect_ratio='16:9',
                                      image_path='', model_version='2.0',
                                      duration_target=15, progress_callback=None, **kwargs):
        if duration_target not in (15, 30):
            raise ValueError('Luồng native Pro hỗ trợ yêu cầu 15 hoặc 30 giây.')
        notify = progress_callback or (lambda message: None)
        errors, media, tasks = [], [], set()

        async def observe_response(response):
            path = urlsplit(response.url).path
            if response.status in (200, 206) and response.headers.get('content-type', '').startswith('video/'):
                media.append(response.url)
            if not any(part in path for part in ('/chat/completion', '/im/chain', '/im/message')):
                return
            try:
                text = await asyncio.wait_for(response.text(), timeout=15)
                error = stream_error(text)
                if error:
                    errors.append(error)
            except (Exception, asyncio.CancelledError):
                pass

        def on_response(response):
            task = asyncio.create_task(observe_response(response))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        page.on('response', on_response)
        try:
            skill_flow = None
            if duration_target == 30:
                from dola_skill_automation import DolaSkillAutomation, record_skill_status
                skill_flow = DolaSkillAutomation(lambda: self._cancel_flag)
                result = await skill_flow.ensure_installed(page, kwargs.get('account_name', ''), notify)
                if kwargs.get('account_name'):
                    record_skill_status(kwargs['account_name'], result)
                skill_editor = await skill_flow.activate(page)
                await verify_skill_token(skill_editor)
                notify('Đã mở chat mới bằng Skill 30s đã cài.')
            else:
                await page.goto('https://www.dola.com/chat/', wait_until='domcontentloaded', timeout=30000)
            await page.locator('[data-testid="chat_input"]').wait_for(timeout=20000)
            # The server-rendered toolbar appears before its click handlers are
            # hydrated; a click at that point is silently ignored by the page.
            await asyncio.sleep(3)
            for label in ('OK', 'Accept all', 'Chấp nhận tất cả'):
                consent = page.get_by_role('button', name=label, exact=True)
                if await consent.count() and await consent.first.is_visible():
                    await consent.first.click(timeout=3000)
            text = await page.locator('body').inner_text()
            if re.search(r'Log In to Unlock|Log in to start creating|not available for guests', text, re.I):
                raise RuntimeError('Tài khoản chưa đăng nhập Dola; chuyển tài khoản khác.')
            # Select Pro through the real UI. Never infer an active model from
            # the existence of a toolbar item or rewrite model IDs in a request.
            await page.get_by_role('button', name=re.compile(r'^(Nhanh|Fast|Pro)(?:\s|$)')).first.wait_for(timeout=20000)
            fast = page.get_by_role('button', name=re.compile(r'^(Nhanh|Fast)'))
            if await fast.count():
                await fast.first.click(timeout=5000)
                pro_option = page.get_by_text('Pro', exact=True)
                try:
                    await pro_option.wait_for(state='visible', timeout=3000)
                except Exception:
                    # Re-observe the current toolbar before one hydration retry.
                    if await fast.count() and await fast.first.is_visible():
                        await fast.first.click(timeout=5000)
                await pro_option.click(timeout=10000)
            await page.get_by_role('button', name=re.compile(r'^Pro(?:\s|$)')).first.wait_for(timeout=10000)
            await asyncio.sleep(1)
            # Consent can mount after the initial page hydration / mode switch.
            consent = page.get_by_role('button', name='OK', exact=True)
            if await consent.count() and await consent.first.is_visible():
                await consent.first.click(timeout=3000)
            notify('Đã chọn Pro native; không nạp extension hoặc sửa payload.')

            files = kwargs.get('file_paths') or []
            images = [image_path] if isinstance(image_path, str) and image_path else list(image_path or [])
            images.extend(files)
            if images:
                inputs = page.locator('input[type="file"]')
                if await inputs.count():
                    await inputs.first.set_input_files(images)
                else:
                    option = page.get_by_text(re.compile(r'^(Tải tập tin hoặc hình ảnh lên|Upload files or images)$'))
                    upload_button = page.get_by_test_id('upload_file_button')
                    # Some Pro layouts open the attach menu on pointer hover;
                    # clicking the same trigger then closes it again.
                    await upload_button.hover(timeout=5000)
                    try:
                        await option.wait_for(state='visible', timeout=1500)
                    except Exception:
                        pass
                    async with page.expect_file_chooser(timeout=10000) as chooser:
                        if await option.is_visible():
                            await option.click(timeout=3000)
                        else:
                            await upload_button.click(timeout=5000)
                            try:
                                await option.wait_for(state='visible', timeout=3000)
                                await option.click(timeout=3000)
                            except Exception:
                                pass
                    await (await chooser.value).set_files(images)
                await asyncio.sleep(4)
                if files:
                    from pathlib import Path
                    for file in files:
                        await page.get_by_text(Path(file).name, exact=False).first.wait_for(state='visible', timeout=30000)

            instruction = (
                f'Tạo đúng MỘT video dài chính xác {duration_target} giây, tỷ lệ {aspect_ratio}. '
                + (f'Ưu tiên Seedance {model_version}; nếu không được, có thể dùng Seedance 2.0 hoặc 2.5. ' if duration_target == 15 else 'Dùng Skill đã chọn, yêu cầu model_version seedance_2.5 và duration 30 trong một lần tạo. ')
                + 'Dùng công cụ tạo video thật; không tự đổi sang 5s/10s, không tạo nhiều clip. '
                'Tôi xác nhận nội dung, tỷ lệ, thời lượng và đồng ý tạo ngay, không cần hỏi lại. '
                'Chỉ báo đang tạo khi có task hợp lệ và cho biết credit còn lại. '
                'Nếu không hỗ trợ hoặc tạo thất bại, báo lỗi thật và dừng.\n\n'
            )
            instruction = kwargs.get('instruction_override', instruction)
            # Preserve the user's timestamps and text. No regex prompt sanitizer.
            editor = page.locator('[contenteditable="true"]').first
            if skill_flow:
                # Keep Dola's selected slash skill token intact.
                await editor.press('Control+End')
                await page.keyboard.insert_text(' ' + instruction + prompt)
            else:
                await editor.fill(instruction + prompt)
            errors.clear()
            media.clear()
            await page.get_by_test_id('chat_input_send_button').evaluate('(el) => el.click()')
            notify(f'Đã gửi yêu cầu {duration_target} giây. Đang kiểm tra task, credit và kết quả thật...')
            start, last_text, acknowledged = time.monotonic(), '', False
            last_asset_check = start
            opened_attachments = set()
            auto_confirmed = False
            while not self._cancel_flag:
                if re.search(r'/chat/\d+', page.url):
                    self.last_chat_url = page.url
                if errors:
                    raise RuntimeError(errors[-1])
                assistant = '\n'.join(await page.locator('[data-message-role="assistant"]').all_inner_texts())
                failure = failure_message(assistant, await page.get_by_text('Không thể tạo video', exact=True).count())
                if failure:
                    raise RuntimeError(f'Dola tạo video thất bại: {failure}')
                if assistant != last_text:
                    if re.search(r'credit|tín dụng|điểm|đang tạo|generating', assistant, re.I):
                        notify(assistant[-1000:])
                    last_text = assistant
                acknowledged = acknowledged or bool(re.search(r'đang tạo|generating|\btask[_ ]?id\b', assistant, re.I))
                if (kwargs.get('auto_confirm') and not auto_confirmed and not acknowledged
                        and re.search(r'please confirm|confirm.*proceed|shall I|would you like me to|xác nhận|bạn.*muốn', assistant, re.I)
                        and time.monotonic() - start > 20):
                    await editor.fill('Confirmed. Generate the requested video now using the selected skill and attached prompt file. Do not ask questions or send status messages; deliver the generated video asset only.')
                    await page.get_by_test_id('chat_input_send_button').evaluate('(el) => el.click()')
                    auto_confirmed = True
                videos = await page.locator('video').evaluate_all(
                    'es => es.map(e => e.currentSrc || e.src).filter(s => /^https?:/.test(s))')
                if videos or media:
                    return (videos or media)[-1]
                if files:
                    attachment = page.get_by_text(re.compile(r'^[^\n]{1,180}\.mp4$', re.I))
                    for i in range(await attachment.count()):
                        item = attachment.nth(i)
                        label = await item.inner_text()
                        if label not in opened_attachments and await item.is_visible():
                            opened_attachments.add(label)
                            await item.click(timeout=5000)
                            break
                elapsed = time.monotonic() - start
                if kwargs.get('check_persisted_assets') and time.monotonic() - last_asset_check > 30:
                    last_asset_check = time.monotonic()
                    try:
                        assets = await read_chat_video_assets(page)
                        if assets:
                            return assets[0]
                    except Exception:
                        pass
                if not acknowledged and not assistant.strip() and elapsed > 90:
                    raise RuntimeError('Dola chưa xác nhận task/credit sau 90s; chuyển tài khoản khác.')
                if elapsed > 900:
                    raise RuntimeError('Timeout 900s: chưa nhận được file video từ Dola.')
                await asyncio.sleep(3)
            raise asyncio.CancelledError()
        finally:
            page.remove_listener('response', on_response)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def execute_skill_batch(self, page, prompts, aspect_ratio='9:16',
                                  model_version='2.5', account_name='',
                                  progress_callback=None, **kwargs):
        self._batch_errors = []
        pending = set()
        async def inspect(response):
            if '/chat/completion' not in response.url:
                return
            try:
                if response.status >= 400:
                    self._batch_errors.append(f'Dola HTTP {response.status}')
                error = stream_error(await asyncio.wait_for(response.text(), timeout=90))
                if error:
                    self._batch_errors.append(error)
            except (Exception, asyncio.CancelledError):
                pass
        def observe(response):
            task = asyncio.create_task(inspect(response))
            pending.add(task)
            task.add_done_callback(pending.discard)
        page.on('response', observe)
        try:
            return await self._execute_skill_batch(page, prompts, aspect_ratio,
                model_version, account_name, progress_callback, **kwargs)
        finally:
            page.remove_listener('response', observe)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    async def _execute_skill_batch(self, page, prompts, aspect_ratio='9:16',
                                  model_version='2.5', account_name='',
                                  progress_callback=None, **kwargs):
        """Install/activate the native skill once, then generate prompts in one Pro chat."""
        from dola_skill_automation import DolaSkillAutomation, record_skill_status, dismiss_consent
        notify = progress_callback or (lambda message: None)
        duration_target = int(kwargs.get('duration_target', 30))
        if duration_target not in (15, 30):
            raise ValueError('Skill duration must be 15 or 30 seconds.')
        flow = DolaSkillAutomation(lambda: self._cancel_flag)
        result = await flow.ensure_installed(page, account_name, notify)
        if account_name:
            record_skill_status(account_name, result)
        editor = await flow.activate(page)
        await verify_skill_token(editor)
        # A newly restored account may show a cookie-consent overlay over the
        # attach menu. Dismiss it before attempting prompt/image uploads.
        await dismiss_consent(page)
        fast = page.get_by_role('button', name=re.compile(r'^(Nhanh|Fast)(?:\s|$)'))
        if await fast.count():
            await fast.first.click(timeout=5000)
            await page.get_by_text('Pro', exact=True).click(timeout=10000)
        await page.get_by_role('button', name=re.compile(r'^Pro(?:\s|$)')).first.wait_for(timeout=10000)
        # The batch is uploaded once, and each numbered prompt runs in order
        # in the same Skill chat. It does not create a new chat per prompt.
        prompt_file = kwargs.get('prompt_file')
        image_path = kwargs.get('image_path')
        if isinstance(image_path, str):
            image_paths = [image_path] if image_path else []
        else:
            image_paths = list(image_path or [])
        upload_paths = []
        from pathlib import Path
        if prompt_file:
            # Each account gets only its assigned numbered prompts, even when
            # the source list contains work assigned to other accounts.
            scoped_file = Path(prompt_file).with_name(
                f"{Path(prompt_file).stem}_{re.sub(r'[^A-Za-z0-9_-]+', '_', account_name or 'account')}_assigned.txt"
            )
            numbers = kwargs.get('prompt_numbers') or list(range(1, len(prompts) + 1))
            scoped_file.write_text(
                "\n\n".join(f"PROMPT {number:02d}\n{prompt.strip()}" for number, prompt in zip(numbers, prompts)),
                encoding='utf-8'
            )
            prompt_file = str(scoped_file)
            upload_paths.append(str(Path(prompt_file).resolve()))
        upload_paths.extend(str(Path(path).resolve()) for path in image_paths)
        if upload_paths:
            upload = page.locator('input[type="file"]')
            if await upload.count():
                await upload.first.set_input_files(upload_paths)
            else:
                button = page.get_by_test_id('upload_file_button')
                option = page.get_by_text(re.compile(r'^(Tải tập tin hoặc hình ảnh lên|Upload files or images)$'))
                uploaded = False
                for attempt in range(3):
                    if not await option.is_visible():
                        await button.click(force=True, timeout=5000, no_wait_after=True)
                        await asyncio.sleep(2 + attempt)
                    try:
                        async with page.expect_file_chooser(timeout=8000) as chooser:
                            await option.click(force=True, timeout=5000, no_wait_after=True)
                        await (await chooser.value).set_files(upload_paths)
                        uploaded = True
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 + attempt)
                if not uploaded:
                    raise RuntimeError('Không mở được menu đính kèm file trong chat Pro.')
            from pathlib import Path
            for filepath in upload_paths:
                await page.get_by_text(Path(filepath).name, exact=False).first.wait_for(state='visible', timeout=30000)
            await asyncio.sleep(float(kwargs.get('action_delay', 4)))
        baseline = set(await read_chat_video_assets(page))
        previous_video_count = await page.locator('video').count()
        results = []
        self.last_batch_results = results
        for index, prompt in enumerate(prompts, 1):
            self._cancel_flag = False
            prompt_number = (kwargs.get('prompt_numbers') or list(range(1, len(prompts) + 1)))[index - 1]
            self.last_prompt_number = prompt_number
            batch_context = {
                'autoDownload': True, 'promptNumber': prompt_number,
                'accountName': account_name, 'batchId': kwargs.get('batch_id', ''),
                'jobId': kwargs.get('job_id', ''),
            }
            await page.evaluate("""(ctx) => {
              window.__SEEDANCE_BATCH_CONTEXT__ = ctx;
              window.postMessage({ type: 'SEEDANCE_BATCH_CONTEXT', context: ctx }, '*');
            }""", batch_context)
            before = set(await read_chat_video_assets(page)) | baseline
            message = (
                f"Go. Generate exactly one standalone video now for PROMPT {index:02d}. "
                f"Use the already selected MianBrothers Seedance 2.5 30s Skill in this Pro chat, "
                f"request a continuous {duration_target}-second {aspect_ratio} video, model Seedance {model_version}. "
                "Do not ask questions or send progress messages. Generate now and return the actual video "
                "through NotifyHuman with its renderable video asset URL after rendering finishes. "
                "If the service refuses or returns a different duration, report the real result.\n\n" + prompt
            )
            if prompt_file:
                numbers = kwargs.get('prompt_numbers') or list(range(1, len(prompts) + 1))
                message = (
                    f"The attached TXT contains your assigned PROMPT {numbers[0]:02d} through PROMPT {numbers[-1]:02d}. "
                    f"Go. For this render, create from PROMPT {prompt_number:02d} to PROMPT {prompt_number:02d} only, "
                    "using the complete description in the TXT. Keep this same conversation for the next prompt. "
                    f"Use the selected Skill in Pro. The user explicitly requests duration {duration_target} seconds for this render: "
                    f"one continuous {duration_target}-second {aspect_ratio} video, Seedance {model_version}. "
                    f"Label the delivered asset PROMPT {prompt_number:02d}. Return the actual finished video through NotifyHuman "
                    "with its renderable video asset URL. The user has confirmed generation; ask no questions and omit progress chatter. "
                    "Report any real service error accurately."
                )
            # Preserve Dola's native selected-Skill token. Filling the
            # contenteditable replaces the token and silently drops the Skill.
            await editor.press('Control+End')
            await page.keyboard.insert_text('\n\n' + message)
            await asyncio.sleep(float(kwargs.get('action_delay', 0)))
            # Dola's current Pro send button ignores synthetic CDP/DOM clicks
            # while a Skill chip is active. Enter is the native submit gesture.
            await editor.press('Enter')
            notify(f"Đã gửi PROMPT {index:02d}/{len(prompts)} trên cùng chat Pro của {account_name}.")
            started = time.monotonic()
            asset = None
            while time.monotonic() - started < 900 and not self._cancel_flag:
                if self._batch_errors:
                    raise RuntimeError(self._batch_errors[-1])
                assistant = '\n'.join(await page.locator('[data-message-role="assistant"]').all_inner_texts())
                if 'from_logout=1' in page.url or re.search(r'đăng nhập để mở khóa|log in to unlock|continue with google', assistant, re.I):
                    raise RuntimeError(f"AUTH_EXPIRED: Dola chuyển account khỏi chat sau khi gửi PROMPT {prompt_number:02d}; không có xác nhận task/credit nên tool đã dừng.")
                failure = failure_message(assistant, await page.get_by_text('Không thể tạo video', exact=True).count())
                if failure:
                    raise RuntimeError(f"PROMPT {index:02d}: {failure}")
                if re.search(r'task_id\s+is\s+empty|content generation for this request is prohibited|retries are not permitted', assistant, re.I):
                    raise RuntimeError(f"Dola từ chối PROMPT {prompt_number:02d}: {assistant[-1200:]}")
                current = await read_chat_video_assets(page)
                new_assets = [url for url in current if url not in before]
                if new_assets:
                    asset = new_assets[0]
                    break
                videos = await page.locator('video').evaluate_all(
                    'es => es.map(e => e.currentSrc || e.src).filter(s => /^https?:/.test(s))')
                if len(videos) > previous_video_count:
                    asset = videos[-1]
                    break
                if kwargs.get('auto_confirm') and re.search(r'please confirm|confirm.*proceed|shall I|xác nhận', assistant, re.I):
                    await editor.press('Control+End')
                    await page.keyboard.insert_text('\n\nConfirmed. Generate this prompt now using the selected 30s Skill.')
                    await editor.press('Enter')
                await asyncio.sleep(8)
            if not asset:
                raise RuntimeError(f"PROMPT {index:02d}: Dola chưa trả video sau 15 phút.")
            results.append({'prompt_number': prompt_number, 'url': asset, 'account_name': account_name})
            self.last_batch_results = results
            baseline.add(asset)
            previous_video_count = await page.locator('video').count()
            on_video_found = kwargs.get('on_video_found')
            if on_video_found:
                callback_result = on_video_found(results[-1])
                if asyncio.iscoroutine(callback_result):
                    await callback_result
            notify(f"Đã bắt được asset PROMPT {index:02d}; chuyển prompt tiếp theo trong cùng chat.")
        return results
