"""Assist an existing Google login; security challenges remain in the browser."""
from urllib.parse import urlparse


class GoogleLoginFlow:
    def __init__(self, email="", password=""):
        self.email = email
        self.password = password
        self.email_sent = False
        self.password_sent = False
        self.returned_to_dola = False
        self.google_clicked = False

    async def step(self, context):
        for page in list(context.pages):
            url = urlparse(page.url)
            # Exact host check: never enter credentials into a redirect/lookalike.
            if url.scheme == "https" and url.hostname == "accounts.google.com":
                if self.email and not self.email_sent:
                    field = page.locator('input[type="email"]').first
                    if await field.count() and await field.is_visible():
                        await field.fill(self.email, timeout=2000)
                        await field.press("Enter", timeout=2000)
                        self.email_sent = True
                        return
                if self.password and not self.password_sent:
                    field = page.locator('input[type="password"]').first
                    if await field.count() and await field.is_visible():
                        await field.fill(self.password, timeout=2000)
                        self.password = ""
                        self.password_sent = True
                        await field.press("Enter", timeout=2000)
                        return
            elif url.scheme == "https" and url.hostname == "console.cloud.google.com":
                # Cloud renders briefly before redirecting to Sign-In. Wait for
                # its account control rather than treating its URL as login proof.
                account = page.locator('[aria-label*="Google Account"], [aria-label*="Tài khoản Google"], a[href*="SignOutOptions"]').first
                if not self.returned_to_dola and await account.count() and await account.is_visible():
                    self.returned_to_dola = True
                    await page.goto("https://www.dola.com/", wait_until="domcontentloaded", timeout=30000)
                    return
            elif url.scheme == "https" and url.hostname in ("www.dola.com", "dola.com"):
                if not self.google_clicked:
                    button = page.get_by_role("button", name="Google", exact=False).first
                    if await button.count() and await button.is_visible():
                        await button.click(timeout=2000)
                        self.google_clicked = True
                        return
