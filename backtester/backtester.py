"""
Backtesting module for strategy validation
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import os

from utils.data_fetcher import PolygonDataFetcher
from scanner.scorer import calculate_score
from utils.config import *

class Backtester:
    def __init__(self):
        self.fetcher = PolygonDataFetcher()
        self.trades = []
        self.results = {}
    
    def run_backtest(self, symbols: List[str], start_date: str, end_date: str):
        """Run backtest on historical data"""
        print(f"[Backtest] Running on {len(symbols)} symbols from {start_date} to {end_date}")
        
        results = []
        for symbol in symbols[:20]:  # limit for demo
            bars = self.fetcher.get_daily_bars(symbol, 30)
            if len(bars) < 10:
                continue
            
            df = pd.DataFrame(bars)
            df['date'] = pd.to_datetime(df['t'])
            df['prev_close'] = df['c'].shift(1)
            df['gap'] = ((df['o'] - df['prev_close']) / df['prev_close']) * 100
            
            # Simulate entries
            for i in range(1, len(df)):
                row = df.iloc[i]
                if row['gap'] < 3 or row['gap'] > 25:
                    continue
                if row['v'] < 200_000:
                    continue
                
                # Simulate trade
                entry = row['o']
                target = entry * 1.20
                stop = entry * 0.95
                
                # Check exit after 1 day
                exit_row = df.iloc[min(i+1, len(df)-1)]
                exit_price = exit_row['c']
                
                if exit_price >= target:
                    pnl = 20.0  # % gain
                elif exit_price <= stop:
                    pnl = -5.0
                else:
                    pnl = ((exit_price - entry) / entry) * 100
                
                results.append({
                    'symbol': symbol,
                    'date': row['date'],
                    'entry': entry,
                    'exit': exit_price,
                    'gap': row['gap'],
                    'volume': row['v'],
                    'pnl': pnl,
                })
        
        self.trades = results
        self._calculate_stats()
        return self.results
    
    def _calculate_stats(self):
        """Calculate performance metrics"""
        if not self.trades:
            self.results = {'error': 'No trades'}
            return
        
        df = pd.DataFrame(self.trades)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] < 0]
        
        self.results = {
            'total_trades': len(df),
            'win_rate': len(wins) / len(df) * 100 if len(df) > 0 else 0,
            'avg_gain': wins['pnl'].mean() if len(wins) > 0 else 0,
            'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
            'profit_factor': abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else 0,
            'total_pnl': df['pnl'].sum(),
            'max_gain': df['pnl'].max(),
            'max_loss': df['pnl'].min(),
        }
        
        print("\n" + "="*50)
        print("📊 BACKTEST RESULTS")
        print("="*50)
        for k, v in self.results.items():
            if isinstance(v, float):
                print(f"{k:20}: {v:.2f}")
            else:
                print(f"{k:20}: {v}")
        print("="*50)
    
    def save_results(self, filename: str = "backtest_results.json"):
        """Save backtest results to file"""
        os.makedirs("data", exist_ok=True)
        with open(f"data/{filename}", "w") as f:
            json.dump({
                'results': self.results,
                'trades': self.trades[:100]  # save first 100
            }, f, indent=2, default=str)
        print(f"[Backtest] Results saved to data/{filename}")
