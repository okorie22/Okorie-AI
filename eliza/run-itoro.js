#!/usr/bin/env node

/**
 * Simple ITORO ElizaOS Runner
 * Direct Node.js execution without Bun dependencies
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import http from 'http';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🚀 Starting ITORO ElizaOS Server (Node.js)...');

// Simple character loader
function loadCharacterFromJson(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    console.error('❌ Failed to load character:', error.message);
    return null;
  }
}

// Load ITORO character
const characterPath = path.join(__dirname, 'character.json');
const itoroCharacter = loadCharacterFromJson(characterPath);

if (!itoroCharacter) {
  console.error('❌ Could not load ITORO character');
  process.exit(1);
}

console.log('✅ Loaded ITORO character:', itoroCharacter.name);

// ITORO Chat Responses
const itoroResponses = [
  "Based on current market analysis, I recommend monitoring BTC/USDT closely. The technical indicators suggest potential volatility ahead.",
  "Your portfolio shows good diversification. Consider adding some altcoins with strong fundamentals to balance your crypto holdings.",
  "Risk management is crucial in trading. Never invest more than 5% of your portfolio in a single position.",
  "The current market sentiment is mixed. I'd suggest waiting for clearer signals before making large moves.",
  "Technical analysis shows support levels holding strong. This could be a good entry point for long-term positions.",
  "Always remember: trading is about probability, not certainty. Risk management should be your top priority.",
  "The crypto market is showing signs of institutional adoption. This could drive prices higher in the medium term.",
  "Market timing is difficult. Focus on quality assets and long-term fundamentals rather than short-term price movements."
];

function getITOROResponse(message) {
  const lowerMessage = message.toLowerCase();

  if (lowerMessage.includes('btc') || lowerMessage.includes('bitcoin')) {
    return "Bitcoin analysis: Currently trading in a consolidation pattern. Watch the $40K-$45K range for breakout signals. Risk management is key here.";
  }

  if (lowerMessage.includes('portfolio') || lowerMessage.includes('holdings')) {
    return "Portfolio review: Ensure proper diversification across assets. Consider 60% BTC/ETH, 30% altcoins, 10% stablecoins for risk management.";
  }

  if (lowerMessage.includes('risk') || lowerMessage.includes('stop loss')) {
    return "Risk management protocol: Never risk more than 2% of your portfolio per trade. Use stop losses at 5-10% below entry. Position sizing matters!";
  }

  if (lowerMessage.includes('buy') || lowerMessage.includes('sell')) {
    return "Trading decision: Always base decisions on technical analysis and market fundamentals. Don't trade based on emotions or FOMO.";
  }

  return itoroResponses[Math.floor(Math.random() * itoroResponses.length)];
}

// Create a chat interface
const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/chat') {
    let body = '';
    req.on('data', chunk => {
      body += chunk.toString();
    });
    req.on('end', () => {
      try {
        const { message } = JSON.parse(body);
        const response = getITOROResponse(message);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          response: response,
          character: itoroCharacter.name
        }));
      } catch (error) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid request' }));
      }
    });
  } else {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>ITORO Trading Advisor Chat</title>
        <style>
          body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
          }
          .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            backdrop-filter: blur(10px);
          }
          h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #ffd700;
          }
          #chat {
            height: 400px;
            overflow-y: auto;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 20px;
            background: rgba(0, 0, 0, 0.3);
          }
          .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
          }
          .user-message {
            background: #007bff;
            margin-left: 100px;
          }
          .itoro-message {
            background: #28a745;
            margin-right: 100px;
          }
          .typing {
            font-style: italic;
            color: #ccc;
          }
          #messageInput {
            width: 70%;
            padding: 10px;
            border: none;
            border-radius: 5px;
            margin-right: 10px;
          }
          button {
            padding: 10px 20px;
            background: #ffd700;
            color: #1e3c72;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
          }
          button:hover {
            background: #ffed4e;
          }
          .status {
            text-align: center;
            margin: 10px 0;
            font-size: 14px;
            color: #ccc;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>🤖 ITORO Trading Advisor</h1>
          <div class="status">🟢 Online - Ready to discuss trading strategies and market analysis</div>

          <div id="chat"></div>

          <div>
            <input type="text" id="messageInput" placeholder="Ask ITORO about trading, portfolio analysis, risk management..." maxlength="500">
            <button onclick="sendMessage()">Send</button>
          </div>
        </div>

        <script>
          const chat = document.getElementById('chat');
          const messageInput = document.getElementById('messageInput');
          let isTyping = false;

          function addMessage(user, message) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + (user === 'You' ? 'user-message' : 'itoro-message');
            messageDiv.innerHTML = '<strong>' + user + ':</strong> ' + message;
            chat.appendChild(messageDiv);
            chat.scrollTop = chat.scrollHeight;
          }

          function showTypingIndicator() {
            if (isTyping) return;
            isTyping = true;
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message itoro-message typing';
            typingDiv.id = 'typing';
            typingDiv.innerHTML = '<strong>ITORO:</strong> <em>is analyzing market data...</em>';
            chat.appendChild(typingDiv);
            chat.scrollTop = chat.scrollHeight;
          }

          function removeTypingIndicator() {
            const typing = document.getElementById('typing');
            if (typing) {
              typing.remove();
              isTyping = false;
            }
          }

          async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            addMessage('You', message);
            messageInput.value = '';
            showTypingIndicator();

            try {
              const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
              });

              const data = await response.json();
              removeTypingIndicator();

              if (data.response) {
                setTimeout(() => addMessage('ITORO', data.response), 500);
              } else {
                addMessage('ITORO', 'I apologize, but I encountered an error processing your request.');
              }
            } catch (error) {
              removeTypingIndicator();
              addMessage('ITORO', 'Connection error. Please try again.');
              console.error('Chat error:', error);
            }
          }

          messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
              sendMessage();
            }
          });

          // Welcome message
          setTimeout(() => {
            addMessage('ITORO', 'Hello! I\\'m ${itoroCharacter.name}, your AI trading advisor. I can help you with portfolio analysis, risk management, market insights, and trading strategies. What would you like to discuss?');
          }, 1000);
        </script>
      </body>
      </html>
    `);
  }
});

const port = process.env.PORT || 3000;
server.listen(port, () => {
  console.log(`✅ ITORO Server running on http://localhost:${port}`);
  console.log(`🤖 ITORO Character: ${itoroCharacter.name}`);
  console.log(`💬 Ready for trading conversations!`);
});

// Handle shutdown
process.on('SIGINT', () => {
  console.log('🛑 Shutting down ITORO server...');
  server.close(() => {
    console.log('✅ Server stopped');
    process.exit(0);
  });
});
