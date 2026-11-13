---
doc_id: it-known-errors-faq
title: Known Errors FAQ
version: "1.0"
valid_from: "2026-01-12"
status: current
area: IT
owner: Service Desk
tags: [FAQ, errors, troubleshooting, Outlook, Teams, printing, VPN]
---

# Known Errors FAQ

### What does "Your account has been locked" mean?

The message `Your account has been locked. Contact your administrator` appears after 10 failed sign-in attempts. The lock clears automatically after 30 minutes. Check that no phone or mail app is using an old password. See it-password-mfa-policy, section "Account lockout".

### How do I reset a forgotten password?

Go to id.example.com/reset, enter your Corvane email and approve the Corvane Verify prompt, then choose a new password of at least 14 characters. See it-password-mfa-policy, section "How to reset your password", for the full procedure.

### Why does Outlook keep asking for my password?

An Outlook password loop usually follows a password change. Close Outlook, open Credential Manager on Windows or Keychain Access on macOS, remove entries containing "Corvane ID", then reopen Outlook and sign in once. If prompts continue, raise a ticket in Assist.

### Teams shows error caa20002. What should I do?

Error `caa20002` means Teams holds an expired sign-in token. Sign out of Teams, quit it completely, and sign in again with your Corvane ID. If the error returns, clear the Teams cache from Settings, then Reset app, and sign in again.

### My VPN says error 809. What does it mean?

Error `809` means SecureLink cannot reach the VPN gateway, usually because the network you are on blocks VPN traffic. Switching the protocol to TLS (port 443) often fixes it. See it-vpn-guide, section "Fixing error 809".

### My print job says "Job held". Why?

`Job held` means the job is waiting at the secure print queue. Walk to any office printer, tap your badge on the reader and select the job to release it. Held jobs are deleted after 24 hours if not released.

### What does "Device not compliant" mean?

`Device not compliant` means DeviceDock found missing updates, disabled encryption or an outdated OS. Open the DeviceDock Company Portal, install pending updates, restart and select Check status. Compliance can take up to 30 minutes to refresh after a fix.

### Why is my Corvane Verify prompt not arriving?

Check that your phone has internet access and that notifications are allowed for Corvane Verify. Open the app and pull down to refresh pending requests. If you have a new phone, the Service Desk must move your registration first.

### I approved an MFA prompt I did not start. What now?

Report it immediately to security@example.com or call ext. 4357, then reset your password at id.example.com/reset. Treat it as a security incident, which is always P1. See it-security-incident-reporting.

### Why can't I install an app from the Company Portal?

An `Installation failed` message in the DeviceDock Company Portal usually means a restart is pending. Restart your laptop and try again. Apps not listed in the Company Portal need a request in Assist. See it-software-catalogue.

### Assist says "Request could not be submitted". What should I do?

The message `Request could not be submitted` appears when your Assist session has expired. Copy your text, refresh the page, sign in again with Corvane ID and resubmit. If Assist itself is down, email servicedesk@example.com instead.

### Orbit HR shows "Access denied" after I changed teams. Why?

`Access denied` in Orbit HR after a move means your role has not been updated yet. Role changes sync overnight. If access is still missing the next working day, ask your manager to confirm the change with People Operations at hr@example.com.

### Lockbox says "Vault locked". How do I open it?

`Vault locked` is normal after 15 minutes of inactivity. Unlock Lockbox with your Corvane ID and Corvane Verify. If you forgot a separate master password set before migration, the Service Desk cannot recover it; you will need a new vault.

### My laptop shows "BitLocker recovery". What do I do?

A `BitLocker recovery` screen appears after some firmware updates. Call the Service Desk on ext. 4357 from another phone; they will read you the recovery key after verifying your identity. Never type the key into a website or chat.

### Why does my external monitor stay black?

Disconnect and reconnect the cable, then press Windows key + P and choose Extend, or on a Mac open System Settings, then Displays. If you use a dock, restart with the dock connected. Faulty docks are replaced through Assist.

### Outlook says "Mailbox full". How do I free space?

The `Your mailbox is full` warning appears at 95 percent of your quota. Empty Deleted Items, delete large attachments and move old mail to your online archive. If you regularly hit the limit, request a larger mailbox in Assist with your manager's approval.

### Why can't I copy files to a USB stick?

USB storage is blocked on all Corvane laptops by design, and Windows shows `Access to removable storage is blocked`. Use OneDrive or a Teams channel to share files instead. See it-acceptable-use-policy for the rules on removable media.

### Teams says "We couldn't connect the call". What can I try?

Check your internet connection, then turn off and on your camera and microphone in Teams settings. If you are on SecureLink VPN, disconnect and try the call again, as calls work better directly. Persistent failures should be logged in Assist.

### My password manager won't fill on a website. Why?

Lockbox only fills on the exact site address the entry was saved with. Open the entry, check the website field and correct it. The Lockbox browser extension must also be enabled; reinstall it from the DeviceDock Company Portal if missing.

### I see "Your session has expired" in several apps at once. Why?

`Your session has expired` across apps means your Corvane ID sign-in ended, often after a password reset or MFA change. Sign out of all apps, sign in again once at id.example.com, then reopen your apps.

### My laptop is very slow after startup. Is something wrong?

Updates often install in the background during the first 20 minutes after startup. Leave the laptop plugged in and connected. If it stays slow for more than a day, raise a ticket in Assist so End-User Computing can check its health.

### Where do I report an error that is not listed here?

Raise a ticket in Assist at assist.example.com, or email servicedesk@example.com. Include the exact message, a screenshot and when it started. For urgent problems call ext. 4357. See gen-service-desk-contacts for hours and priorities.
