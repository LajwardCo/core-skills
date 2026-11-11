#!/bin/bash
# mac-guard: one dim line - how much is used, and whether to start another AI session.
# Thresholds scale with installed RAM, so this works on any Mac.
GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
MAXCHATS=$(( GB * 5 / 24 )); [ "$MAXCHATS" -lt 2 ] && MAXCHATS=2
TIGHT=$(( GB / 3 )); DANGER=$(( GB * 2 / 3 ))

SW=$(sysctl -n vm.swapusage | sed -E 's/.*used = ([0-9.]+)M.*/\1/'); SW=${SW%.*}; SW=$((SW/1024))
AG=$(pgrep -x claude | wc -l | tr -d ' ')
FIX=()
if pgrep -qf 'Virtualization.VirtualMachine.xpc'; then
  NC=$(docker ps -q 2>/dev/null | wc -l | tr -d ' ')
  [ "$NC" = "0" ] && FIX+=("quit Docker (8G, nothing running in it)") || FIX+=("quit Docker (8G, $NC containers - keep only if in use)")
fi
[ "$(pgrep -f 'chrome-headless-shell|ms-playwright' | wc -l | tr -d ' ')" -gt 0 ] && FIX+=("pkill -f chrome-headless-shell")
[ "$(ps -Ao ppid,command | awk '$1==1' | grep -c 'claude-[0-9]*.*scratchpad')" -gt 0 ] && FIX+=('pkill -f "claude-[0-9]*.*scratchpad"')
[ "$AG" -gt "$MAXCHATS" ] && FIX+=("close $((AG-MAXCHATS)) finished chats")

if [ "$SW" -ge "$DANGER" ] || [ "$AG" -gt $((MAXCHATS+3)) ]; then V="don't start another"
elif [ "$SW" -ge "$TIGHT" ] || [ "$AG" -gt "$MAXCHATS" ]; then V="free something first"
else V="ok to start"; fi
[ ${#FIX[@]} -gt 0 ] && J=" - $(IFS=';'; echo "${FIX[*]}" | sed 's/;/; /g')" || J=""
printf '\033[90mmac-guard: %sG swap, %s chats - %s%s\033[0m\n' "$SW" "$AG" "$V" "$J"
