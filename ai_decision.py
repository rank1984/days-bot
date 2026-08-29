from google import genai
import json

class AIDecisionLayer:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)

    def analyze_setup(self, stock_data, quant_data):
        prompt = f"""
        You are a Quant AI Decision Engine for Small-Cap Gap-and-Go strategies.
        Do NOT invent prices. Only evaluate the setup quality.
        
        STOCK DATA:
        Ticker: {stock_data.get('ticker')}
        Price: {stock_data.get('price')}
        Gap: {stock_data.get('gap_pct')}%
        PM Volume: {stock_data.get('pm_volume')}
        
        QUANT ENGINE DATA:
        Regime: {quant_data.get('regime')}
        
        Evaluate this setup and return ONLY a valid JSON format with the following keys:
        - "decision": String (Must be "TRADE", "WAIT", or "NO TRADE". Use WAIT for good setups needing a breakout).
        - "score": Integer (0-100).
        - "trade_type": String (e.g. "BREAKOUT", "QUICK SCALP").
        - "expected_hold": String (e.g. "5-30 min").
        - "confidence": String ("HIGH", "MEDIUM", "LOW").
        - "why_list": Array of 3-4 short strings explaining why this is good.
        - "risks_list": Array of 2-3 short strings outlining the risks.
        
        JSON OUTPUT ONLY:
        """
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            # Clean formatting if Gemini adds markdown blocks
            raw_text = response.text.replace('```json', '').replace('```', '').strip()
            decision_data = json.loads(raw_text)
            return decision_data
        except Exception as e:
            print(f"[AI Layer] Error: {e}")
            # Safe Fallback
            return {
                "decision": "WAIT",
                "score": 50,
                "trade_type": "UNKNOWN",
                "expected_hold": "N/A",
                "confidence": "LOW",
                "why_list": ["AI Evaluation Failed"],
                "risks_list": ["System Error"]
            }
