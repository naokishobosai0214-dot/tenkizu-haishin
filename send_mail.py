"""Gmail で天気図を送る。画像は添付し、本文にページのURLを書く。
環境変数: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, REPORT_TO(空なら GMAIL_ADDRESS), PAGE_URL(任意)
"""
import os
import smtplib
from email.message import EmailMessage


def send(subject, pages, site_dir):
    sender = os.environ["GMAIL_ADDRESS"]
    to = os.environ.get("REPORT_TO") or sender
    page_url = os.environ.get("PAGE_URL", "")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    lines = [subject, ""] + [f"・{p['title']}" for p in pages]
    if page_url:
        lines += ["", f"ページで見る: {page_url}"]
    lines += ["", "出典：気象庁ホームページ"]
    msg.set_content("\n".join(lines))
    for p in pages:
        with open(os.path.join(site_dir, p["full"]), "rb") as f:
            msg.add_attachment(f.read(), maintype="image", subtype="jpeg", filename=p["full"])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    print(f"  メール送信: {to}")
