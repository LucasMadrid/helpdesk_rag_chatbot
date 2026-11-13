---
doc_id: it-vpn-guide
title: SecureLink VPN Setup and Troubleshooting
version: "1.0"
valid_from: "2025-06-02"
status: current
area: IT
owner: Network & Connectivity
tags: [VPN, SecureLink, remote access, error 809, troubleshooting]
---

# SecureLink VPN Setup and Troubleshooting

SecureLink 5.2 is the Corvane VPN client. You need it to reach internal systems such as file shares, build servers and the warehouse test environments when you are not on the office network. The VPN gateway is vpn.example.com and you sign in with your Corvane ID and Corvane Verify. SecureLink is supported on Corvane-managed Windows and macOS laptops only. Personal devices cannot connect.

## Windows

These steps apply to Windows 11 laptops enrolled in DeviceDock.

### Step 1: Check your laptop is compliant

Open the DeviceDock Company Portal and confirm your laptop shows as compliant. SecureLink refuses to connect from a laptop that is missing security updates or has disk encryption turned off.

### Step 2: Open the DeviceDock Company Portal

Select Start, type Company Portal and open it. Sign in with your Corvane ID if prompted.

### Step 3: Install the client

Search for SecureLink, select SecureLink 5.2 for Windows and select Install. The installation takes about three minutes. Do not download SecureLink from anywhere else.

### Step 4: Restart your laptop

Restart once the installation finishes so that the network driver loads.

### Step 5: Connect

Open SecureLink from the system tray. The gateway vpn.example.com is filled in for you. Select Connect, sign in with your Corvane ID and approve the Corvane Verify prompt. The tray icon turns green when you are connected.

## macOS

These steps apply to macOS 14 or later on laptops enrolled in DeviceDock.

### Step 1: Check your laptop is compliant

Open the DeviceDock Company Portal and confirm your Mac shows as compliant. SecureLink refuses to connect from a Mac that is missing security updates or has FileVault turned off.

### Step 2: Open the DeviceDock Company Portal

Open Finder, go to Applications and open Company Portal. Sign in with your Corvane ID if prompted.

### Step 3: Install the client

Search for SecureLink, select SecureLink 5.2 for macOS and select Install. The installation takes about three minutes. Do not download SecureLink from anywhere else.

### Step 4: Allow the system extension

When macOS shows "System Extension Blocked", open System Settings, go to Privacy & Security and select Allow next to SecureLink. Then allow the VPN configuration when prompted.

### Step 5: Connect

Open SecureLink from the menu bar. The gateway vpn.example.com is filled in for you. Select Connect, sign in with your Corvane ID and approve the Corvane Verify prompt. The menu bar icon turns green when you are connected.

## Error codes

SecureLink shows a numbered error when a connection fails. Find the code in the table below before you raise a ticket.

| Code | Message shown | Usual cause | What to do |
|---|---|---|---|
| `809` | `Error 809: The network connection between your computer and the VPN server could not be established` | The local network blocks VPN traffic, often hotel, café or guest Wi-Fi | Follow "Fixing error 809" below |
| `691` | `Error 691: The remote connection was denied because the user name and password combination you provided is not recognized` | Wrong or recently changed Corvane ID password, or the account is locked | Sign in at id.example.com to check your password; see it-password-mfa-policy |
| `720` | `Error 720: A connection to the remote computer could not be established` | The SecureLink network adapter is damaged | Uninstall SecureLink, restart, and reinstall from the Company Portal |
| `13801` | `Error 13801: IKE authentication credentials are unacceptable` | The device certificate is missing or expired | Open the Company Portal and select Sync, then restart; if it persists, raise a ticket |
| `SL-1042` | `SL-1042: Device not compliant` | DeviceDock reports the laptop as non-compliant | Install pending updates from the Company Portal, restart and select Check status |

## Fixing error 809

Error 809 means SecureLink could not reach the gateway at all. Your password is not the problem. The full message reads `Error 809: The network connection between your computer and the VPN server could not be established`. It almost always comes from the network you are on, not from your laptop. Work through these steps in order and try to connect after each one:

1. Check you have internet access by opening any website. If nothing loads, fix your Wi-Fi first.
2. If you are on hotel, airport, café or other public Wi-Fi, complete any sign-in page the network shows in your browser, then try again.
3. In SecureLink, open Settings and change Protocol from Automatic to TLS (port 443). Many public networks block the default protocol but allow port 443.
4. Turn off any other VPN or "secure browsing" app on the laptop.
5. If you are at home, restart your router. Some home routers need "VPN passthrough" turned on in their settings.
6. Connect through your phone's hotspot. If SecureLink works on the hotspot, the original network is blocking VPN traffic and there is nothing more to fix on your laptop.
7. If error 809 appears on every network, including a hotspot, restart the laptop and reinstall SecureLink from the Company Portal.

If none of these steps work, raise a ticket in Assist under Network and VPN, or call the Service Desk on ext. 4357 (+353 1 555 0100 from outside). Include the error code, the network you were on and the time of the attempt. Tickets are passed to Network & Connectivity if Tier 1 cannot resolve them.

## Getting help

The IT Service Desk is available Monday to Friday, 08:00 to 18:00 Irish time. Outside those hours, only P1 incidents are handled: call ext. 4357 and choose option 9. Not being able to connect to the VPN on your own is normally a P3 unless a customer outage depends on it. See gen-service-desk-contacts for priorities and response times.
