"""
Pattern Service - Main Orchestrator
Coordinates all components for real-time pattern detection
"""

import os
import time
import signal
import sys
from datetime import datetime
from typing import List, Dict

from pattern_detector import PatternDetector
from data_fetcher import BinanceDataFetcher
from alert_system import AlertSystem
from pattern_storage import PatternStorage


class PatternService:
    """
    Main service orchestrator for pattern detection.
    Coordinates data fetching, pattern detection, alerts, and storage.
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        scan_interval: int = 300,
        data_timeframe: str = '1d',
        deepseek_api_key: str = None,
        enable_desktop_notifications: bool = True,
        db_path: str = 'patterns.db'
    ):
        """
        Initialize pattern service.
        
        Args:
            symbols: List of symbols to monitor (default: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'])
            scan_interval: Seconds between scans (default: 300 = 5 minutes)
            data_timeframe: OHLCV timeframe (default: '1d')
            deepseek_api_key: DeepSeek API key for AI analysis
            enable_desktop_notifications: Enable desktop notifications
            db_path: SQLite database path
        """
        # Configuration
        self.symbols = symbols or ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
        self.scan_interval = scan_interval
        self.data_timeframe = data_timeframe
        
        # Initialize components
        print("\n" + "="*80)
        print("PATTERN SERVICE INITIALIZATION")
        print("="*80)
        
        print(f"\n[CONFIG] Symbols: {', '.join(self.symbols)}")
        print(f"[CONFIG] Scan Interval: {scan_interval} seconds ({scan_interval/60:.1f} minutes)")
        print(f"[CONFIG] Data Timeframe: {data_timeframe}")
        
        self.pattern_detector = PatternDetector(ohlcv_history_length=100)
        self.data_fetcher = BinanceDataFetcher()
        self.alert_system = AlertSystem(
            deepseek_api_key=deepseek_api_key,
            enable_desktop_notifications=enable_desktop_notifications
        )
        self.storage = PatternStorage(db_path=db_path)
        
        # State tracking
        self.running = False
        self.scan_count = 0
        self.patterns_detected = 0
        self.last_scan_time = None
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
        print("\n[PATTERN SERVICE] All components initialized successfully")
        print("="*80 + "\n")
    
    def scan_symbol(self, symbol: str) -> List[Dict]:
        """
        Scan a single symbol for patterns.
        
        Args:
            symbol: Trading symbol to scan
            
        Returns:
            List of detected patterns
        """
        try:
            print(f"\n[SCAN] {symbol} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch OHLCV data
            ohlcv_data = self.data_fetcher.get_ohlcv(symbol, self.data_timeframe, limit=100)
            
            if ohlcv_data is None or len(ohlcv_data) == 0:
                print(f"[SCAN] {symbol} - No data available")
                return []
            
            # Update pattern detector with new data
            self.pattern_detector.update_data(ohlcv_data)
            
            # Scan for patterns
            detected_patterns = self.pattern_detector.scan_for_patterns()
            
            if detected_patterns:
                print(f"[SCAN] {symbol} - {len(detected_patterns)} pattern(s) detected")
                
                # Process each detected pattern
                for pattern_data in detected_patterns:
                    # Generate AI analysis and send alerts
                    alert_result = self.alert_system.send_alert(pattern_data, symbol, include_ai_analysis=True)
                    
                    # Store pattern in database
                    pattern_id = self.storage.save_pattern(
                        symbol,
                        pattern_data,
                        alert_result['ai_analysis']
                    )
                    
                    if pattern_id > 0:
                        self.patterns_detected += 1
                
                return detected_patterns
            else:
                print(f"[SCAN] {symbol} - No patterns detected")
                return []
                
        except Exception as e:
            print(f"[ERROR] Scan failed for {symbol}: {e}")
            return []
    
    def scan_all_symbols(self) -> Dict[str, List[Dict]]:
        """
        Scan all configured symbols.
        
        Returns:
            Dictionary mapping symbols to detected patterns
        """
        results = {}
        
        for symbol in self.symbols:
            patterns = self.scan_symbol(symbol)
            if patterns:
                results[symbol] = patterns
            time.sleep(1)  # Small delay between symbol scans
        
        return results
    
    def run(self):
        """
        Main service loop - continuously scan for patterns.
        """
        self.running = True
        
        print("\n" + "="*80)
        print("PATTERN SERVICE STARTED")
        print("="*80)
        print(f"Monitoring: {', '.join(self.symbols)}")
        print(f"Scan interval: {self.scan_interval} seconds")
        print(f"Press Ctrl+C to stop")
        print("="*80 + "\n")
        
        try:
            while self.running:
                scan_start = time.time()
                self.scan_count += 1
                
                print(f"\n{'='*80}")
                print(f"SCAN #{self.scan_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*80}")
                
                # Scan all symbols
                results = self.scan_all_symbols()
                
                # Summary
                total_patterns = sum(len(patterns) for patterns in results.values())
                scan_duration = time.time() - scan_start
                
                print(f"\n{'='*80}")
                print(f"SCAN #{self.scan_count} COMPLETE")
                print(f"{'='*80}")
                print(f"Duration: {scan_duration:.2f}s")
                print(f"Patterns detected: {total_patterns}")
                print(f"Total patterns today: {self.patterns_detected}")
                
                if results:
                    print(f"\nDetected patterns:")
                    for symbol, patterns in results.items():
                        for p in patterns:
                            print(f"  {symbol}: {p['pattern']} ({p['direction']}) - {p['confidence']:.1%}")
                
                print(f"{'='*80}")
                
                # Wait for next scan
                self.last_scan_time = datetime.now()
                wait_time = max(0, self.scan_interval - scan_duration)
                
                if wait_time > 0:
                    print(f"\n[WAIT] Next scan in {wait_time:.0f} seconds...")
                    time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n\n[SERVICE] Received interrupt signal")
        finally:
            self.stop(None, None)
    
    def run_once(self) -> Dict[str, List[Dict]]:
        """
        Run a single scan (useful for testing).
        
        Returns:
            Dictionary mapping symbols to detected patterns
        """
        print("\n[SERVICE] Running single scan...")
        results = self.scan_all_symbols()
        
        total_patterns = sum(len(patterns) for patterns in results.values())
        print(f"\n[SERVICE] Scan complete - {total_patterns} patterns detected")
        
        return results
    
    def stop(self, signum, frame):
        """
        Stop the service gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        if not self.running:
            return
        
        self.running = False
        
        print("\n\n" + "="*80)
        print("PATTERN SERVICE STOPPING")
        print("="*80)
        print(f"Total scans completed: {self.scan_count}")
        print(f"Total patterns detected: {self.patterns_detected}")
        
        # Get statistics from storage
        stats = self.storage.get_pattern_statistics()
        if stats:
            print(f"\n[STATISTICS]")
            print(f"  Patterns in database: {stats['total_patterns']}")
            print(f"  Average confidence: {stats['average_confidence']:.1%}")
            print(f"  Pattern distribution: {stats['pattern_counts']}")
        
        print("\n[SERVICE] Stopped successfully")
        print("="*80 + "\n")
        
        sys.exit(0)
    
    def get_status(self) -> Dict:
        """
        Get current service status.
        
        Returns:
            Dictionary with service status information
        """
        stats = self.storage.get_pattern_statistics()
        
        return {
            'running': self.running,
            'scan_count': self.scan_count,
            'patterns_detected': self.patterns_detected,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'symbols': self.symbols,
            'scan_interval': self.scan_interval,
            'data_timeframe': self.data_timeframe,
            'database_stats': stats
        }


def main():
    """Main entry point for pattern service"""
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                  SolPattern Detector Service                         ║
    ║              Real-time Pattern Detection with AI Analysis            ║
    ║                      86% Historical Win Rate                         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Configuration (can be moved to config file)
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT']
    scan_interval = 300  # 5 minutes
    data_timeframe = '1d'  # Daily candles (as backtested)
    
    # Get DeepSeek API key from environment
    deepseek_api_key = os.getenv('DEEPSEEK_KEY')
    
    # Initialize and run service
    service = PatternService(
        symbols=symbols,
        scan_interval=scan_interval,
        data_timeframe=data_timeframe,
        deepseek_api_key=deepseek_api_key,
        enable_desktop_notifications=True,
        db_path='patterns.db'
    )
    
    # Run continuously
    service.run()


if __name__ == "__main__":
    main()

