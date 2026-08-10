from discord_desktop import DiscordDesktopBridge

ok, detail = DiscordDesktopBridge.launch_accessible_discord()

if ok:
    print("Discord launched with renderer accessibility enabled.")
    print(detail)
else:
    print("ERROR:", detail)
    raise SystemExit(1)
