#!/bin/bash
# Load translator prompt text from file or stdin into DB.
# Usage:
#   cat prompt.txt | ./load_prompt.sh "Акыда"
#   ./load_prompt.sh "Акыда" < prompt.txt
#   ./load_prompt.sh "Акыда" prompt.txt

PROMPT_NAME="${1:?Usage: $0 <prompt_name> [file]}"
USER_ID=6839947992
DB_CONTAINER=multi_ai_bot_db
DB_USER=multi_ai_bot
DB_NAME=multi_ai_bot

if [ -n "$2" ] && [ -f "$2" ]; then
    PROMPT_TEXT=$(cat "$2")
else
    PROMPT_TEXT=$(cat)
fi

if [ -z "$PROMPT_TEXT" ]; then
    echo "Error: empty prompt text"
    exit 1
fi

echo "Loading prompt '$PROMPT_NAME' (${#PROMPT_TEXT} chars)..."

# Escape single quotes for SQL
ESCAPED=$(echo "$PROMPT_TEXT" | sed "s/'/''/g")

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Upsert: update if exists, insert if not
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM translator_prompts WHERE user_id = $USER_ID AND name = '$PROMPT_NAME') THEN
        UPDATE translator_prompts SET system_prompt = '$ESCAPED' WHERE user_id = $USER_ID AND name = '$PROMPT_NAME';
        RAISE NOTICE 'Updated existing prompt "%"', '$PROMPT_NAME';
    ELSE
        INSERT INTO translator_prompts (user_id, name, system_prompt, is_active) VALUES ($USER_ID, '$PROMPT_NAME', '$ESCAPED', false);
        RAISE NOTICE 'Inserted new prompt "%"', '$PROMPT_NAME';
    END IF;
END \$\$;
SELECT id, name, is_active, length(system_prompt) as chars FROM translator_prompts WHERE user_id = $USER_ID;
EOF
