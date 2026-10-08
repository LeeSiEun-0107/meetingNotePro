#!/usr/bin/env bash
# 껍데기. 내용은 ~/.claude/skills/todo-guard/scripts/session-start.sh 에 한 벌만 둔다.
#   exec 가 아니라 source 로 부른다. exec 는 bash 를 한 번 더 띄우는데
#   윈도우에서 그 한 번이 0.6초다. 도구를 부를 때마다 붙는 시간이다
. "$HOME/.claude/skills/todo-guard/scripts/session-start.sh"
