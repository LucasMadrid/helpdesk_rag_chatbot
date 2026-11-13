---
doc_id: it-security-incident-reporting
title: Phishing and Security Incident Reporting
version: "1.0"
valid_from: "2025-11-03"
status: current
area: IT
owner: Security Operations
tags: [security, incident, phishing, lost device, stolen device, remote wipe]
---

# Phishing and Security Incident Reporting

This page explains what a security incident is, how to report one and what happens after you report it. It applies to everyone who uses Corvane systems, including contractors.

## Reporting a suspected incident

A security incident is any event that could put Corvane or customer data, accounts or systems at risk. Typical examples are clicking a link in a phishing email, entering your Corvane ID password on a page you do not trust, approving a Corvane Verify prompt you did not start, finding malware warnings on your laptop, sending customer data to the wrong recipient, or noticing that someone has used your account. You do not need to be sure that something is an incident before you report it.

Corvane follows a no-blame approach to reporting. Mistakes happen, and attackers design phishing messages to fool careful people. Nobody is disciplined for reporting their own mistake honestly and quickly. What causes real damage is silence: an attacker who has your password or a session on your laptop can move to other systems within minutes.

Before you report, note what you can without delaying the report: the time you noticed the problem, what you clicked or entered, the sender address or website, and whether you used a Corvane laptop or another device. Do not try to investigate yourself, do not forward suspicious attachments to colleagues and do not delete the evidence.

Report to Security Operations by email at security@example.com, or call the IT Service Desk on ext. 4357 (+353 1 555 0100 from outside). Outside Service Desk hours (Monday to Friday 08:00–18:00 Irish time), call ext. 4357 and choose option 9 to reach the on-call engineer. A security incident is always handled as P1, which means a response within 15 minutes and a target resolution or containment within 4 hours.

You must report a suspected security incident within 1 hour of noticing it. This applies at any time of day, including evenings and weekends. If you entered your password on a suspicious page, change it at id.example.com/reset straight after you report, not instead of reporting.

## Reporting a phishing email

1. Do not click links, open attachments or reply to the message.
2. In Outlook, select the message and choose the Report Phish button on the toolbar. This sends a copy to Security Operations and removes the message from your inbox.
3. If you use Outlook on a phone or the button is missing, forward the message as an attachment to security@example.com and then delete it.
4. If you clicked a link, opened an attachment or entered any information, treat it as a security incident and report it within 1 hour as described above, in addition to pressing Report Phish.
5. Watch for a confirmation email from Security Operations. If the message was a simulated phishing test, you will see a short training page instead.

## Lost or stolen devices

1. Report a lost or stolen laptop or any device with Corvane email or data on it within 24 hours, and as soon as possible. Call ext. 4357 (option 9 outside hours) rather than emailing, because you may not have access to your account.
2. Give the device type, when and where you last had it, and whether it was locked.
3. Security Operations locks the device and starts a remote wipe through DeviceDock. A remote wipe erases all data on the device the next time it connects to the internet, so tell the Service Desk if you think you might still find it.
4. Your Corvane ID sessions are revoked and you will be asked to set a new password and re-enrol Corvane Verify.
5. If the device was stolen, report the theft to the local police and add the police reference number to the Assist ticket.
6. End-User Computing arranges a replacement laptop. See it-laptop-request for the replacement process.

## What happens next

Security Operations confirms receipt of your report, contains the threat, for example by resetting credentials or isolating a laptop from the network, and keeps you updated in an Assist ticket. Some incidents involving personal data must be notified to regulators within strict deadlines, which is another reason fast reporting matters. Once the incident is closed, you may be asked to join a short review so the team can improve controls. Questions about this process go to security@example.com.
