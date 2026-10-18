# Demo Script: 2 Minutes 30 Seconds

## 0:00-0:15 | Set the scene

Open the Cram page and say: "Cram is a voice study assistant. Alexa+ is simulated here; the tools themselves are served over MCP."

## 0:15-0:35 | Add notes

Use the example link or type: "add notes about photosynthesis: Photosynthesis lets plants convert sunlight into glucose. Chlorophyll absorbs light. Plants use glucose for energy."

Show the confirmation and the topic with its note count.

## 0:35-0:55 | Summarize

Ask: "Summarize photosynthesis." Show the short reply and its `used: summarize_topic` line.

## 0:55-1:45 | Take a three-question quiz

Ask: "Quiz me on photosynthesis for three questions." Answer each question in turn. Point out that Cram asks one question at a time, gives the next question after each answer, and ends with the score.

## 1:45-2:00 | Choose what to review

Ask: "What should I review?" Show the weakest topic and the reason based on quiz accuracy.

## 2:00-2:30 | Show MCP and the code

Open the MCP Inspector connected to `http://localhost:8000/mcp` and show the seven discovered tools. Briefly show `src/cram/server.py` for the tool definitions and `src/cram/db.py` for the SQLite storage. Mention that a real Alexa+ client would replace the simulated Strands chat agent.