# Fix Extension Auto-Download & Implement 30s Video Bypass

## Problem Analysis

### Issue 1: Extension auto-downloads old videos on page load
**Root Cause:** `seedance_auto_dl` defaulted to `true` (`!== false`), so every time Chrome opens and the extension sniffs old video URLs from chat history, it triggers downloads.

**Status:** ✅ Already Fixed — Changed default to `false` (`=== true`). Now auto-download only triggers when explicitly toggled ON by user. Videos save to `Downloads/Seedance_Videos/` subfolder.

---

### Issue 2: 30s video bypass not working — why the extension fetch hook never fires

**Root Cause Discovered by analyzing the original tool logs:**

The original SD tool (`SD bản gốc`) uses a **completely different page**: `https://www.dola.com/chat/create-image`

> **This is the critical difference.** The original tool navigates to the **Create Image/Video studio page** (`/chat/create-image`), clicks the "Video" tab, and then submits the prompt there. On that page, Dola sends the generation request via `/chat/completion` POST with a JSON body containing `"duration": 10`, `"model_version": "2.0"`, etc. — which the extension's fetch hook intercepts and replaces with `duration: 31` + `model: 2.5`.
>
> Our current tool uses the **regular chat page** (`/chat/`) with the "Tạo video" chat skill button. On that page, Dola uses `/im/message` and `/im/chain` APIs which do NOT include `duration` in the POST body — so the bypass regex never matches anything.

**Original tool flow (from logs):**
```
1. Navigate to https://www.dola.com/chat/create-image
2. Click tab 'Video' on the create-image page
3. Set bypass via localStorage: __dolaTargetDur=31, __dolaDurBypass=1
4. Skip Model/Duration selection on UI (leave defaults)
5. Upload reference image (optional)
6. Type prompt in the text input area
7. Press Enter → Dola fires /chat/completion POST with "duration":10 in body
8. Extension fetch hook intercepts → replaces "duration":10 → "duration":31 + model "2.0"→"2.5"
9. Server receives modified request → generates 30s video with Seedance 2.5
10. Extension captures video link from SSE response stream
```

**Our current (broken) flow:**
```
1. Navigate to https://www.dola.com/chat/ (regular chat)
2. Click "Tạo video" skill button in chat
3. Set bypass via localStorage + CDP
4. Type prompt → Press Enter
5. Dola sends /im/chain/single and /im/message → NO "duration" in body
6. Extension bypass regex finds nothing to replace → video is 10s
```

## Proposed Changes

### Component 1: Extension — Auto-Download Fix (✅ DONE)
- Changed `seedance_auto_dl !== false` → `=== true` (default OFF)
- Added `Seedance_Videos/` subfolder prefix for organized downloads

### Component 2: Tool Backend — Switch to create-image Page for 15s/30s
- Navigate to `/chat/create-image` instead of `/chat/`
- Click the "Video" tab on the create-image studio page
- Activate extension bypass before submitting
- Input prompt in the create-image text area
- Press Enter → triggers `/chat/completion` POST which extension intercepts
- Wait for video in the SSE response stream
