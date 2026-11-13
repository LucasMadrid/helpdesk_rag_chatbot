---
doc_id: it-password-mfa-policy
title: Password and MFA Policy
version: "2.0"
valid_from: "2025-09-01"
status: current
supersedes: "1.0"
area: IT
owner: Security Operations
tags: [password, passphrase, MFA, Corvane ID, FIDO2, reset, lockout]
---

# Password and MFA Policy

## Purpose and scope

This policy sets the rules for passwords and multi-factor authentication (MFA) on Corvane ID, the single sign-on account every Corvane employee and contractor uses to reach email, Teams, Assist, Orbit HR, SecureLink VPN and customer-facing admin consoles. It applies to everyone with a Corvane ID account in Dublin, Lisbon and fully remote roles. Service accounts and break-glass administrator accounts are covered by a separate Infrastructure Engineering standard.

Version 2.0 replaces version 1.0 from 1 September 2025. The main changes are longer passwords without complexity rules, no scheduled expiry, and the removal of SMS as an MFA method.

Your Corvane ID password protects company and customer data. Never share it, never write it down, and never reuse it on any other website. Store it, and any other work credentials, in Lockbox, the approved password manager.

## Password requirements

All Corvane ID passwords must meet the requirements below. Corvane ID enforces them automatically when you set or change a password.

| Requirement | Rule |
|---|---|
| Minimum length | 14 characters; passphrases are allowed and there are no complexity rules |
| Expiry | No scheduled expiry; reset only when a compromise is suspected |
| MFA method | Corvane Verify push notification or a FIDO2 security key; SMS is no longer accepted |
| Account lockout | 10 failed sign-in attempts lock the account for 30 minutes |
| Password history | The last 12 passwords cannot be reused |

A passphrase of four or more unrelated words, such as a short sentence only you would think of, is easier to remember and harder to guess than a short complex password. Corvane ID checks every new password against a list of known breached passwords and rejects any match. Passwords must not contain your name, your username, the word "Corvane" or the name of a customer.

## Password expiry

Corvane ID passwords no longer expire on a schedule. You only need to change your password when a compromise is suspected, for example if you entered it on a phishing page, approved an MFA prompt you did not start, or Security Operations asks you to. In that case, reset it straight away using the procedure below and report the incident with the "Report Phish" button in Outlook or to security@example.com.

Change your password from a Corvane laptop connected to the office network or to SecureLink VPN, so that your laptop picks up the new password straight away.

## Multi-factor authentication

MFA is mandatory for every Corvane ID account. You can choose one of two methods:

- A push notification in the Corvane Verify app on your phone, with number matching.
- A FIDO2 security key plugged into or tapped on your laptop. Keys are issued by the Service Desk on request through Assist.

SMS codes were removed as an MFA method on 1 September 2025. If you still have SMS registered, Corvane ID asks you to set up Corvane Verify at your next sign-in. You can manage your methods under Security settings on id.example.com.

Never approve an MFA prompt that you did not start yourself. An unexpected prompt means someone else may know your password. Deny the prompt, reset your password, and report it to security@example.com.

## Account lockout

After 10 failed sign-in attempts your Corvane ID account is locked for 30 minutes. The lock clears on its own; you do not need to contact anyone. While locked, applications show the message `Your account has been locked. Contact your administrator`. Repeated lockouts usually mean that an old password is saved on a phone or in a mail app, so check those devices first. If you need access before the 30 minutes are up, call the Service Desk on ext. 4357.

## How to reset your password

If you have forgotten your password, you can reset it yourself without contacting the Service Desk:

1. Go to id.example.com/reset from any browser.
2. Enter your Corvane email address and select Next.
3. Approve the prompt that appears in the Corvane Verify app on your phone, entering the number shown on screen.
4. Enter a new password that meets the requirements in the table above.
5. Enter the new password again to confirm it and select Reset password.
6. Sign in on your Corvane laptop while connected to the office network or to SecureLink VPN, so the laptop stores the new password.
7. Update the password in Outlook mobile, Teams mobile and any other app that prompts you.

If you do not have access to Corvane Verify, use a FIDO2 key if you have one registered, or contact the IT Service Desk on ext. 4357. The Service Desk will verify your identity by video call before resetting the password.

## Lost or replaced MFA device

If you lose the phone you use for Corvane Verify, or lose your FIDO2 key, contact the Service Desk on ext. 4357 so they can remove the old method and register a new one. A lost phone that has Corvane apps installed must also be reported to Security Operations. See it-security-incident-reporting.

## Exceptions and enforcement

Exceptions to this policy require written approval from Security Operations and are reviewed every six months. Accounts that do not meet this policy may be disabled until they comply.
