#!/usr/bin/env bash
set -euo pipefail

out="${1:-contextweaver_caption_demo.mp4}"
font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
bold="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=0x08111f:s=1280x720:r=30:d=90" \
  -f lavfi -i "anullsrc=r=48000:cl=stereo:d=90" \
  -filter_complex "
    [0:v]
    drawbox=x=0:y=0:w=1280:h=10:color=0x51d8c6:t=fill,
    drawbox=x=0:y=680:w='1280*t/90':h=6:color=0x51d8c6:t=fill,

    drawtext=fontfile=${bold}:text='CONTEXTWEAVER':fontcolor=0x51d8c6:fontsize=28:x=70:y=54,
    drawtext=fontfile=${font}:text='Inspectable ambient intelligence for Alexa+':fontcolor=white@0.65:fontsize=20:x=70:y=94,

    drawtext=fontfile=${bold}:text='Nothing leaves this screen':fontcolor=white:fontsize=58:x=(w-text_w)/2:y=240:enable='between(t,0,14.9)',
    drawtext=fontfile=${bold}:text='without a reason.':fontcolor=0x51d8c6:fontsize=58:x=(w-text_w)/2:y=310:enable='between(t,0,14.9)',
    drawtext=fontfile=${font}:text='A visible action graph for intent, context, tools, and permission.':fontcolor=white@0.78:fontsize=25:x=(w-text_w)/2:y=414:enable='between(t,0,14.9)',

    drawtext=fontfile=${bold}:text='THE REQUEST':fontcolor=0x51d8c6:fontsize=25:x=95:y=180:enable='between(t,15,29.9)',
    drawbox=x=95:y=235:w=1090:h=175:color=0x12243a:t=fill:enable='between(t,15,29.9)',
    drawtext=fontfile=${font}:text='Plan my next 1 hour and 30 minutes.':fontcolor=white:fontsize=38:x=(w-text_w)/2:y=270:enable='between(t,15,29.9)',
    drawtext=fontfile=${font}:text='I need to leave by 9\:00 PM.':fontcolor=white:fontsize=38:x=(w-text_w)/2:y=330:enable='between(t,15,29.9)',
    drawtext=fontfile=${bold}:text='Parsed correctly\: 90 minutes | departure 21\:00':fontcolor=0x51d8c6:fontsize=27:x=(w-text_w)/2:y=465:enable='between(t,15,29.9)',

    drawtext=fontfile=${bold}:text='INTENT  →  CONTEXT  →  TOOLS  →  DECISION':fontcolor=white:fontsize=35:x=(w-text_w)/2:y=155:enable='between(t,30,44.9)',
    drawbox=x=90:y=270:w=230:h=110:color=0x15334d:t=fill:enable='between(t,30,44.9)',
    drawbox=x=350:y=270:w=230:h=110:color=0x15334d:t=fill:enable='between(t,30,44.9)',
    drawbox=x=610:y=270:w=230:h=110:color=0x15334d:t=fill:enable='between(t,30,44.9)',
    drawbox=x=870:y=270:w=230:h=110:color=0x15334d:t=fill:enable='between(t,30,44.9)',
    drawtext=fontfile=${bold}:text='CAPTURED':fontcolor=0x51d8c6:fontsize=24:x=135:y=312:enable='between(t,30,44.9)',
    drawtext=fontfile=${bold}:text='3 / 18 facts':fontcolor=0x51d8c6:fontsize=24:x=392:y=312:enable='between(t,30,44.9)',
    drawtext=fontfile=${bold}:text='4 nodes':fontcolor=0x51d8c6:fontsize=24:x=670:y=312:enable='between(t,30,44.9)',
    drawtext=fontfile=${bold}:text='REVIEW':fontcolor=0x51d8c6:fontsize=24:x=935:y=312:enable='between(t,30,44.9)',
    drawtext=fontfile=${font}:text='Only decision-changing context enters the run.':fontcolor=white@0.75:fontsize=27:x=(w-text_w)/2:y=470:enable='between(t,30,44.9)',

    drawtext=fontfile=${bold}:text='BUDGET-SAFE BY CONSTRUCTION':fontcolor=white:fontsize=43:x=(w-text_w)/2:y=155:enable='between(t,45,59.9)',
    drawtext=fontfile=${bold}:text='90 planned minutes · 4 reversible nodes':fontcolor=0x51d8c6:fontsize=46:x=(w-text_w)/2:y=260:enable='between(t,45,59.9)',
    drawtext=fontfile=${font}:text='Every minute is accounted for. The departure constraint is protected.':fontcolor=white@0.78:fontsize=25:x=(w-text_w)/2:y=360:enable='between(t,45,59.9)',
    drawtext=fontfile=${font}:text='4 action nodes · 4 explanation receipts · 0 writes':fontcolor=white:fontsize=29:x=(w-text_w)/2:y=435:enable='between(t,45,59.9)',

    drawtext=fontfile=${bold}:text='HUMAN CHECKPOINT':fontcolor=0x51d8c6:fontsize=25:x=95:y=175:enable='between(t,60,74.9)',
    drawtext=fontfile=${bold}:text='Review before Alexa+ speaks or acts.':fontcolor=white:fontsize=45:x=95:y=235:enable='between(t,60,74.9)',
    drawbox=x=95:y=340:w=310:h=90:color=0x1d6f65:t=fill:enable='between(t,60,74.9)',
    drawbox=x=435:y=340:w=260:h=90:color=0x3a2230:t=fill:enable='between(t,60,74.9)',
    drawtext=fontfile=${bold}:text='APPROVE':fontcolor=white:fontsize=30:x=175:y=369:enable='between(t,60,74.9)',
    drawtext=fontfile=${bold}:text='CANCEL':fontcolor=white:fontsize=30:x=500:y=369:enable='between(t,60,74.9)',
    drawtext=fontfile=${font}:text='Read, suggest, and write remain distinct capabilities.':fontcolor=white@0.75:fontsize=26:x=95:y=490:enable='between(t,60,74.9)',

    drawtext=fontfile=${bold}:text='SELECTIVE. INSPECTABLE. REVERSIBLE.':fontcolor=white:fontsize=44:x=(w-text_w)/2:y=200:enable='between(t,75,89.9)',
    drawtext=fontfile=${font}:text='Live prototype':fontcolor=white@0.65:fontsize=22:x=(w-text_w)/2:y=300:enable='between(t,75,89.9)',
    drawtext=fontfile=${bold}:text='contextweaver-alexa.floot.app':fontcolor=0x51d8c6:fontsize=33:x=(w-text_w)/2:y=350:enable='between(t,75,89.9)',
    drawtext=fontfile=${font}:text='Simulated Alexa+ + MCP · explicit demo inputs · no production data access':fontcolor=white@0.72:fontsize=22:x=(w-text_w)/2:y=430:enable='between(t,75,89.9)',

    fade=t=in:st=0:d=0.7,fade=t=out:st=89:d=1[v]
  " \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 96k -movflags +faststart -shortest "$out"

ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height \
  -of default=noprint_wrappers=1 "$out"
