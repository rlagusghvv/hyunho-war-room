# TOOLS.md - Local Notes

Skills define *how* tools work. This file is for *your* specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases  
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras
- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH
- home-server → 192.168.1.100, user: admin

### TTS
- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## CoupElephant 운영 고정 메모 (재발 방지)
- LaunchAgent 라벨: `com.splui.coupelephant-server`
- 실제 작업 디렉토리(중요): `/Users/kimhyunhomacmini/.openclaw/workspace/coupang-automation`
- 재시작 명령:
  - `launchctl kickstart -kp gui/$(id -u)/com.splui.coupelephant-server`
- 재시작 직후 필수 확인(둘 다 통과해야 완료 보고):
  - `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/health` → `200`
  - `curl -s -o /dev/null -w "%{http_code}" https://app2.splui.com/health` → `200`
- 헷갈리기 쉬운 포인트:
  - Desktop 경로(`.../couplus-clone`) 기준으로 판단하지 말고, **launchctl의 working directory 기준**으로 확인할 것.

Add whatever helps you do your job. This is your cheat sheet.
