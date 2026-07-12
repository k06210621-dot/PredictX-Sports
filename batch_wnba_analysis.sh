#!/bin/bash
# 批次 WNBA AI 分析 + 結算
API="https://predictx-sports-production.up.railway.app/api/run_analysis"

GAME_IDS=(
  "c7f675d4-487b-4089-aac0-64ac5f24ea25"
  "f781b5f1-e1f8-4974-80c7-63285a05d57e"
  "3791a075-fd33-4d7b-b719-ef3f78ba58f3"
  "6d29a2f3-2bb1-4a2e-a847-83490184b7bf"
  "e78028d7-a149-4276-87f3-f3b638f16476"
  "201d609c-2466-496b-9fdb-622c07405256"
  "dda36ccf-3b0d-48ad-a330-fb79d8483072"
  "ecea30e8-c094-43fc-919c-9f0648cd60c7"
  "1412017b-e150-4212-b7ab-34ace3fabcb4"
  "965c9941-f872-4300-b7ff-75d85774b066"
  "9812851c-d162-411e-a9f1-d590cbc49ec2"
  "9f753329-42a2-456f-b140-624fce071bb1"
  "58b0c02b-878b-4fd0-a96f-a2776f912822"
  "419e49ca-a003-4fed-8b95-3e0b2754c4fc"
  "aa2266e4-9df2-4409-a2ef-210fb74688eb"
  "c5385049-e3b2-461c-b7a7-710a5701e030"
  "cc6a4688-6a2d-4923-b587-b04e3ca46196"
  "0ee4cf7d-0a4c-4c47-960c-5111b1f2b2b7"
  "555bbf49-6e41-499b-bcbb-2553fd1f65a9"
  "f83f9031-5fc4-4052-ae8e-f76e118352ac"
  "a7da265a-e6e5-47f1-adff-615e7668ac2e"
  "aeb83ad9-6f34-4865-a46d-263c4bbe0517"
  "b3ddf9d8-a8e4-4e0e-b2ad-69e661ae929e"
  "83feecd3-f405-4844-8f70-22dabefd3052"
  "bdc0b4fa-dfa1-40f2-838b-fbac5142212f"
  "c4ceba51-21fc-40f1-a490-61541c789b06"
)

OK=0
FAIL=0
i=0
TOTAL=${#GAME_IDS[@]}

for gid in "${GAME_IDS[@]}"; do
  i=$((i+1))
  echo -n "[$i/$TOTAL] $gid... "
  RESP=$(curl -s -X POST "$API" -H "Content-Type: application/json" -d "{\"game_id\": \"$gid\", \"max_count\": 1}" --max-time 180 2>&1)
  ANALYZED=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('analyzed',0))" 2>/dev/null)
  if [ "$ANALYZED" = "1" ]; then
    echo "OK"
    OK=$((OK+1))
  else
    echo "FAIL: $RESP"
    FAIL=$((FAIL+1))
  fi
  sleep 1
done

echo ""
echo "=== 批次分析完成 ==="
echo "成功: $OK/$TOTAL"
echo "失敗: $FAIL/$TOTAL"