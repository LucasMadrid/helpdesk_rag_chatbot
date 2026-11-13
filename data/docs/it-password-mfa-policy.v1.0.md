---
doc_id: it-password-mfa-policy
title: Password and MFA Policy
version: "1.0"
valid_from: "2024-03-01"
valid_to: "2025-08-31"
status: superseded
area: IT
owner: Security Operations
tags: [password, MFA, Corvane ID, reset, lockout]
---

# Password and MFA Policy

## Purpose and scope

This policy sets the rules for passwords and multi-factor authentication (MFA) on Corvane ID, the single sign-on account every Corvane employee and contractor uses to reach email, Teams, Assist, Orbit HR, SecureLink VPN and customer-facing admin consoles. It applies to everyone with a Corvane ID account in Dublin, Lisbon and fully remote roles. Service accounts and break-glass administrator accounts are covered by a separate Infrastructure Engineering standard.

Your Corvane ID password protects company and customer data. Never share it, never write it down, and never reuse it on any other website. Store it, and any other work credentials, in Lockbox, the approved password manager.

## Password requirements

All Corvane ID passwords must meet the requirements below. Corvane ID enforces them automatically when you set or change a password.

| Requirement | Rule |
|---|---|
| Minimum length | 12 characters, with at least one uppercase letter, one lowercase letter, one number and one symbol |
| Expiry | Every 90 days; a warning is shown 14 days before expiry |
| MFA method | SMS code or Corvane Verify push notification |
| Account lockout | 5 failed sign-in attempts lock the account for 15 minutes |
| Password history | The last 5 passwords cannot be reused |

Passwords must not contain your name, your username, the word "Corvane" or the name of a customer. Simple substitutions such as replacing "a" with "@" do not make a weak password strong.

## Password expiry

Corvane ID passwords expire every 90 days. Starting 14 days before the expiry date, you see a banner at every sign-in asking you to change your password. This 14-day window is the grace period: you can keep working normally, but you should change your password before it ends. If you ignore the banner and the password expires, you are forced to change it at your next sign-in before you can reach any application.

Change your password from a Corvane laptop connected to the office network or to SecureLink VPN, so that your laptop picks up the new password straight away. If you change it from a phone or a personal device, lock and unlock your laptop while connected to the VPN afterwards.

## Multi-factor authentication

MFA is mandatory for every Corvane ID account. You can choose one of two methods:

- A one-time code sent by SMS to your registered mobile number.
- A push notification in the Corvane Verify app on your phone.

Corvane Verify is recommended because SMS codes can be intercepted. You register your MFA method the first time you sign in, and you can change it at any time under Security settings on id.example.com.

Never approve an MFA prompt that you did not start yourself. An unexpected prompt means someone else may know your password. Deny the prompt, change your password, and report it to security@example.com.

## Account lockout

After 5 failed sign-in attempts your Corvane ID account is locked for 15 minutes. The lock clears on its own; you do not need to contact anyone. Repeated lockouts may indicate that an old password is saved on a phone or in a mail app, so check those devices first.

## How to reset your password

If you have forgotten your password, you can reset it yourself without contacting the Service Desk:

1. Go to id.example.com/reset from any browser.
2. Enter your Corvane email address and select Next.
3. Answer your 3 security questions. You set these up when you first registered with Corvane ID.
4. Enter a new password that meets the requirements in the table above.
5. Enter the new password again to confirm it and select Reset password.
6. Sign in on your Corvane laptop while connected to the office network or to SecureLink VPN, so the laptop stores the new password.
7. Update the password in Outlook mobile, Teams mobile and any other app that prompts you.

If you cannot answer your security questions, or the reset page reports an error, contact the IT Service Desk on ext. 4357. The Service Desk will verify your identity before resetting the password.

## Lost or replaced MFA device

If you lose the phone you use for MFA, or change your mobile number, contact the Service Desk on ext. 4357 so they can remove the old method. A lost phone that has Corvane apps installed must also be reported to Security Operations. See it-security-incident-reporting.

## Exceptions and enforcement

Exceptions to this policy require written approval from Security Operations and are reviewed every six months. Accounts that do not meet this policy may be disabled until they comply.
