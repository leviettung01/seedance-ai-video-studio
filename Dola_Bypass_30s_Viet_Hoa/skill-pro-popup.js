document.addEventListener('DOMContentLoaded', async () => {
  const toggle = document.getElementById('seedance-auto-skill');
  const label = document.getElementById('seedance-skill-popup-status');
  toggle.checked = !!(await chrome.storage.local.get('seedance_auto_skill')).seedance_auto_skill;
  toggle.addEventListener('change', () => chrome.storage.local.set({seedance_auto_skill:toggle.checked}));
  document.getElementById('seedance-prepare-skill').addEventListener('click', async () => {
    try {
      const tabs = await chrome.tabs.query({active:true,currentWindow:true});
      const tab = tabs[0];
      if (!tab?.id || !/^https:\/\/(www\.)?dola\.com\//.test(tab.url || '')) throw new Error('Mở tab Dola đã đăng nhập trước.');
      const result = await chrome.tabs.sendMessage(tab.id, {type:'SEEDANCE_PREPARE_SKILL_PRO'});
      label.textContent = result?.ok ? 'Đang chuẩn bị trên tab Dola. Chưa gửi prompt tạo video.' : result?.error || 'Không thể chuẩn bị Skill.';
    } catch (error) { label.textContent = error.message; }
  });
});
