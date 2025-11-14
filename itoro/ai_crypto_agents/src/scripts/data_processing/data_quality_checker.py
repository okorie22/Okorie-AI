#!/usr/bin/env python3
"""
📊 Anarcho Capital's Data Quality Checker
Validate price data accuracy, market data freshness, and data integrity
Built with love by Anarcho Capital 🚀
"""

import os
import sys
import time
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

@dataclass
class DataQualityStatus:
    """Data quality status information"""
    data_type: str
    status: str  # 'excellent', 'good', 'degraded', 'poor'
    freshness_score: float  # 0-1
    accuracy_score: float  # 0-1
    completeness_score: float  # 0-1
    last_update: Optional[datetime]
    issues: List[str]
    recommendations: List[str]
    performance_metrics: Dict[str, Any]

class DataQualityChecker:
    """Monitor data quality across all data sources"""
    
    def __init__(self):
        self.data_sources = {
            'price_data': {
                'cache_file': 'src/data/token_cache.db',
                'max_age_minutes': 5,
                'min_accuracy_threshold': 0.95
            },
            'sentiment_data': {
                'history_file': 'src/data/sentiment_history.csv',
                'max_age_hours': 2,
                'min_accuracy_threshold': 0.8
            },
            'whale_data': {
                'ranked_file': 'src/data/whale_dump/ranked_whales.json',
                'history_file': 'src/data/whale_dump/whale_history.csv',
                'max_age_hours': 24,
                'min_accuracy_threshold': 0.9
            },
            'chart_data': {
                'charts_dir': 'src/data/charts',
                'max_age_hours': 6,
                'min_accuracy_threshold': 0.85
            },
            'portfolio_data': {
                'db_file': 'data/portfolio_history_paper.db',
                'max_age_minutes': 1,
                'min_accuracy_threshold': 0.99
            }
        }
    
    def check_price_data_quality(self) -> DataQualityStatus:
        """Check price data quality and freshness"""
        issues = []
        recommendations = []
        
        try:
            import sqlite3
            
            # Check price cache database
            cache_file = self.data_sources['price_data']['cache_file']
            if not os.path.exists(cache_file):
                issues.append("Price cache database not found")
                return DataQualityStatus(
                    data_type='price_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            conn = sqlite3.connect(cache_file)
            cursor = conn.cursor()
            
            # Check cache table structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='price_cache'")
            if not cursor.fetchone():
                issues.append("Price cache table not found")
                conn.close()
                return DataQualityStatus(
                    data_type='price_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Get recent price data
            cursor.execute("""
                SELECT COUNT(*) as total_entries,
                       COUNT(CASE WHEN timestamp > datetime('now', '-5 minutes') THEN 1 END) as recent_entries,
                       AVG(CASE WHEN timestamp > datetime('now', '-1 hour') THEN 1.0 ELSE 0.0 END) as hourly_freshness
                FROM price_cache
            """)
            result = cursor.fetchone()
            
            total_entries = result[0] or 0
            recent_entries = result[1] or 0
            hourly_freshness = result[2] or 0.0
            
            # Calculate freshness score
            freshness_score = recent_entries / max(total_entries, 1)
            
            # Check for stale data
            cursor.execute("""
                SELECT COUNT(*) FROM price_cache 
                WHERE timestamp < datetime('now', '-1 hour')
            """)
            stale_count = cursor.fetchone()[0] or 0
            
            if stale_count > total_entries * 0.5:
                issues.append(f"High percentage of stale price data: {stale_count}/{total_entries}")
            
            # Check for price anomalies
            cursor.execute("""
                SELECT COUNT(*) FROM price_cache 
                WHERE price <= 0 OR price > 1000000
            """)
            anomaly_count = cursor.fetchone()[0] or 0
            
            if anomaly_count > 0:
                issues.append(f"Price anomalies detected: {anomaly_count} invalid prices")
            
            # Calculate accuracy score
            accuracy_score = 1.0 - (anomaly_count / max(total_entries, 1))
            
            # Calculate completeness score
            completeness_score = min(1.0, total_entries / 100)  # Assume 100 entries is complete
            
            # Get last update time
            cursor.execute("SELECT MAX(timestamp) FROM price_cache")
            last_update_str = cursor.fetchone()[0]
            last_update = None
            if last_update_str:
                try:
                    last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                except:
                    last_update = None
            
            conn.close()
            
            # Determine status
            if freshness_score >= 0.8 and accuracy_score >= 0.95 and completeness_score >= 0.8:
                status = 'excellent'
            elif freshness_score >= 0.6 and accuracy_score >= 0.9 and completeness_score >= 0.6:
                status = 'good'
            elif freshness_score >= 0.4 and accuracy_score >= 0.8:
                status = 'degraded'
            else:
                status = 'poor'
            
            if freshness_score < 0.5:
                recommendations.append("Consider increasing price update frequency")
            if accuracy_score < 0.9:
                recommendations.append("Implement price validation to filter anomalies")
            if completeness_score < 0.7:
                recommendations.append("Increase price data collection coverage")
            
            performance_metrics = {
                'total_entries': total_entries,
                'recent_entries': recent_entries,
                'stale_count': stale_count,
                'anomaly_count': anomaly_count,
                'hourly_freshness': hourly_freshness
            }
            
        except Exception as e:
            issues.append(f"Error checking price data: {str(e)}")
            return DataQualityStatus(
                data_type='price_data',
                status='poor',
                freshness_score=0.0,
                accuracy_score=0.0,
                completeness_score=0.0,
                last_update=None,
                issues=issues,
                recommendations=recommendations,
                performance_metrics={}
            )
        
        return DataQualityStatus(
            data_type='price_data',
            status=status,
            freshness_score=freshness_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            last_update=last_update,
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_sentiment_data_quality(self) -> DataQualityStatus:
        """Check sentiment data quality and freshness"""
        issues = []
        recommendations = []
        
        try:
            sentiment_file = self.data_sources['sentiment_data']['history_file']
            
            if not os.path.exists(sentiment_file):
                issues.append("Sentiment history file not found")
                return DataQualityStatus(
                    data_type='sentiment_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Read sentiment data
            df = pd.read_csv(sentiment_file)
            
            if df.empty:
                issues.append("Sentiment data is empty")
                return DataQualityStatus(
                    data_type='sentiment_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Check data freshness
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                last_update = df['timestamp'].max()
                hours_old = (datetime.now() - last_update).total_seconds() / 3600
                
                if hours_old > 2:
                    issues.append(f"Sentiment data is {hours_old:.1f} hours old")
                
                freshness_score = max(0, 1 - (hours_old / 24))  # Decay over 24 hours
            else:
                issues.append("No timestamp column in sentiment data")
                freshness_score = 0.0
                last_update = None
            
            # Check data accuracy (sentiment scores should be between -1 and 1)
            if 'sentiment_score' in df.columns:
                invalid_scores = df[(df['sentiment_score'] < -1) | (df['sentiment_score'] > 1)]
                accuracy_score = 1.0 - (len(invalid_scores) / len(df))
                
                if len(invalid_scores) > 0:
                    issues.append(f"Invalid sentiment scores found: {len(invalid_scores)} entries")
            else:
                issues.append("No sentiment_score column found")
                accuracy_score = 0.0
            
            # Check data completeness
            required_columns = ['timestamp', 'sentiment_score', 'source']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                issues.append(f"Missing required columns: {missing_columns}")
            
            completeness_score = 1.0 - (len(missing_columns) / len(required_columns))
            
            # Determine status
            if freshness_score >= 0.8 and accuracy_score >= 0.9 and completeness_score >= 0.9:
                status = 'excellent'
            elif freshness_score >= 0.6 and accuracy_score >= 0.8 and completeness_score >= 0.8:
                status = 'good'
            elif freshness_score >= 0.4 and accuracy_score >= 0.7:
                status = 'degraded'
            else:
                status = 'poor'
            
            if freshness_score < 0.5:
                recommendations.append("Increase sentiment data collection frequency")
            if accuracy_score < 0.8:
                recommendations.append("Implement sentiment score validation")
            if completeness_score < 0.8:
                recommendations.append("Ensure all required columns are present")
            
            performance_metrics = {
                'total_entries': len(df),
                'columns': list(df.columns),
                'missing_columns': missing_columns,
                'hours_old': hours_old if 'timestamp' in df.columns else None
            }
            
        except Exception as e:
            issues.append(f"Error checking sentiment data: {str(e)}")
            return DataQualityStatus(
                data_type='sentiment_data',
                status='poor',
                freshness_score=0.0,
                accuracy_score=0.0,
                completeness_score=0.0,
                last_update=None,
                issues=issues,
                recommendations=recommendations,
                performance_metrics={}
            )
        
        return DataQualityStatus(
            data_type='sentiment_data',
            status=status,
            freshness_score=freshness_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            last_update=last_update,
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_whale_data_quality(self) -> DataQualityStatus:
        """Check whale data quality and freshness"""
        issues = []
        recommendations = []
        
        try:
            ranked_file = self.data_sources['whale_data']['ranked_file']
            history_file = self.data_sources['whale_data']['history_file']
            
            # Check ranked whales file
            if not os.path.exists(ranked_file):
                issues.append("Ranked whales file not found")
                return DataQualityStatus(
                    data_type='whale_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            with open(ranked_file, 'r') as f:
                whale_data = json.load(f)
            
            # Check data freshness
            last_update = None
            if 'last_updated' in whale_data:
                try:
                    last_update = datetime.fromisoformat(whale_data['last_updated'].replace('Z', '+00:00'))
                    hours_old = (datetime.now() - last_update).total_seconds() / 3600
                    
                    if hours_old > 24:
                        issues.append(f"Whale data is {hours_old:.1f} hours old")
                    
                    freshness_score = max(0, 1 - (hours_old / 48))  # Decay over 48 hours
                except:
                    issues.append("Invalid timestamp format in whale data")
                    freshness_score = 0.0
            else:
                issues.append("No timestamp in whale data")
                freshness_score = 0.0
            
            # Check data accuracy
            whales = whale_data.get('whales', [])
            if not whales:
                issues.append("No whale data found")
                return DataQualityStatus(
                    data_type='whale_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Validate whale data structure
            required_fields = ['address', 'score', 'pnl_30d']
            invalid_whales = 0
            
            for whale in whales:
                if not all(field in whale for field in required_fields):
                    invalid_whales += 1
                elif not isinstance(whale.get('score', 0), (int, float)):
                    invalid_whales += 1
                elif not isinstance(whale.get('pnl_30d', 0), (int, float)):
                    invalid_whales += 1
            
            accuracy_score = 1.0 - (invalid_whales / len(whales))
            
            if invalid_whales > 0:
                issues.append(f"Invalid whale data entries: {invalid_whales}/{len(whales)}")
            
            # Check data completeness
            completeness_score = len(whales) / 100  # Assume 100 whales is complete
            
            # Determine status
            if freshness_score >= 0.8 and accuracy_score >= 0.9 and completeness_score >= 0.8:
                status = 'excellent'
            elif freshness_score >= 0.6 and accuracy_score >= 0.8 and completeness_score >= 0.6:
                status = 'good'
            elif freshness_score >= 0.4 and accuracy_score >= 0.7:
                status = 'degraded'
            else:
                status = 'poor'
            
            if freshness_score < 0.5:
                recommendations.append("Update whale data more frequently")
            if accuracy_score < 0.8:
                recommendations.append("Validate whale data structure")
            if completeness_score < 0.7:
                recommendations.append("Collect more whale data")
            
            performance_metrics = {
                'whale_count': len(whales),
                'invalid_entries': invalid_whales,
                'hours_old': hours_old if last_update else None
            }
            
        except Exception as e:
            issues.append(f"Error checking whale data: {str(e)}")
            return DataQualityStatus(
                data_type='whale_data',
                status='poor',
                freshness_score=0.0,
                accuracy_score=0.0,
                completeness_score=0.0,
                last_update=None,
                issues=issues,
                recommendations=recommendations,
                performance_metrics={}
            )
        
        return DataQualityStatus(
            data_type='whale_data',
            status=status,
            freshness_score=freshness_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            last_update=last_update,
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_chart_data_quality(self) -> DataQualityStatus:
        """Check chart data quality and freshness"""
        issues = []
        recommendations = []
        
        try:
            charts_dir = self.data_sources['chart_data']['charts_dir']
            
            if not os.path.exists(charts_dir):
                issues.append("Charts directory not found")
                return DataQualityStatus(
                    data_type='chart_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Get chart files
            chart_files = [f for f in os.listdir(charts_dir) if f.endswith(('.png', '.csv'))]
            
            if not chart_files:
                issues.append("No chart files found")
                return DataQualityStatus(
                    data_type='chart_data',
                    status='poor',
                    freshness_score=0.0,
                    accuracy_score=0.0,
                    completeness_score=0.0,
                    last_update=None,
                    issues=issues,
                    recommendations=recommendations,
                    performance_metrics={}
                )
            
            # Check file freshness
            recent_files = 0
            last_update = None
            
            for file in chart_files:
                file_path = os.path.join(charts_dir, file)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if last_update is None or file_time > last_update:
                    last_update = file_time
                
                if file_time > datetime.now() - timedelta(hours=6):
                    recent_files += 1
            
            freshness_score = recent_files / len(chart_files)
            
            if freshness_score < 0.5:
                issues.append(f"Only {recent_files}/{len(chart_files)} chart files are recent")
            
            # Check file integrity
            corrupted_files = 0
            for file in chart_files:
                file_path = os.path.join(charts_dir, file)
                try:
                    if file.endswith('.png'):
                        # Check if PNG file is valid
                        with open(file_path, 'rb') as f:
                            header = f.read(8)
                            if not header.startswith(b'\x89PNG\r\n\x1a\n'):
                                corrupted_files += 1
                    elif file.endswith('.csv'):
                        # Check if CSV file is readable
                        pd.read_csv(file_path, nrows=1)
                except:
                    corrupted_files += 1
            
            accuracy_score = 1.0 - (corrupted_files / len(chart_files))
            
            if corrupted_files > 0:
                issues.append(f"Corrupted chart files: {corrupted_files}/{len(chart_files)}")
            
            # Check completeness (should have charts for major tokens)
            expected_tokens = ['SOL', 'WIF', 'BOME', 'JTO', 'PYTH']
            completeness_score = 0.0
            
            for token in expected_tokens:
                if any(token in file for file in chart_files):
                    completeness_score += 0.2
            
            if completeness_score < 0.8:
                issues.append(f"Missing charts for some tokens (completeness: {completeness_score:.1%})")
            
            # Determine status
            if freshness_score >= 0.8 and accuracy_score >= 0.9 and completeness_score >= 0.8:
                status = 'excellent'
            elif freshness_score >= 0.6 and accuracy_score >= 0.8 and completeness_score >= 0.6:
                status = 'good'
            elif freshness_score >= 0.4 and accuracy_score >= 0.7:
                status = 'degraded'
            else:
                status = 'poor'
            
            if freshness_score < 0.5:
                recommendations.append("Generate charts more frequently")
            if accuracy_score < 0.8:
                recommendations.append("Fix corrupted chart files")
            if completeness_score < 0.8:
                recommendations.append("Generate charts for all monitored tokens")
            
            performance_metrics = {
                'total_files': len(chart_files),
                'recent_files': recent_files,
                'corrupted_files': corrupted_files,
                'expected_tokens': expected_tokens
            }
            
        except Exception as e:
            issues.append(f"Error checking chart data: {str(e)}")
            return DataQualityStatus(
                data_type='chart_data',
                status='poor',
                freshness_score=0.0,
                accuracy_score=0.0,
                completeness_score=0.0,
                last_update=None,
                issues=issues,
                recommendations=recommendations,
                performance_metrics={}
            )
        
        return DataQualityStatus(
            data_type='chart_data',
            status=status,
            freshness_score=freshness_score,
            accuracy_score=accuracy_score,
            completeness_score=completeness_score,
            last_update=last_update,
            issues=issues,
            recommendations=recommendations,
            performance_metrics=performance_metrics
        )
    
    def check_all_data_quality(self) -> Dict[str, DataQualityStatus]:
        """Check quality of all data sources"""
        statuses = {}
        
        statuses['price_data'] = self.check_price_data_quality()
        statuses['sentiment_data'] = self.check_sentiment_data_quality()
        statuses['whale_data'] = self.check_whale_data_quality()
        statuses['chart_data'] = self.check_chart_data_quality()
        
        return statuses
    
    def get_data_quality_summary(self) -> Dict[str, Any]:
        """Get overall data quality summary"""
        statuses = self.check_all_data_quality()
        
        total_sources = len(statuses)
        excellent_sources = sum(1 for status in statuses.values() if status.status == 'excellent')
        good_sources = sum(1 for status in statuses.values() if status.status == 'good')
        degraded_sources = sum(1 for status in statuses.values() if status.status == 'degraded')
        poor_sources = sum(1 for status in statuses.values() if status.status == 'poor')
        
        # Calculate average scores
        avg_freshness = sum(status.freshness_score for status in statuses.values()) / total_sources
        avg_accuracy = sum(status.accuracy_score for status in statuses.values()) / total_sources
        avg_completeness = sum(status.completeness_score for status in statuses.values()) / total_sources
        
        # Count total issues
        total_issues = sum(len(status.issues) for status in statuses.values())
        total_recommendations = sum(len(status.recommendations) for status in statuses.values())
        
        # Find worst performing data source
        worst_source = min(statuses.items(), key=lambda x: x[1].freshness_score + x[1].accuracy_score + x[1].completeness_score)
        
        return {
            'total_sources': total_sources,
            'excellent_sources': excellent_sources,
            'good_sources': good_sources,
            'degraded_sources': degraded_sources,
            'poor_sources': poor_sources,
            'avg_freshness_score': avg_freshness,
            'avg_accuracy_score': avg_accuracy,
            'avg_completeness_score': avg_completeness,
            'total_issues': total_issues,
            'total_recommendations': total_recommendations,
            'worst_source': worst_source[0],
            'quality_percentage': ((excellent_sources + good_sources) / total_sources * 100) if total_sources > 0 else 0
        }
    
    def get_data_quality_recommendations(self) -> List[str]:
        """Get comprehensive data quality recommendations"""
        statuses = self.check_all_data_quality()
        all_recommendations = []
        
        for status in statuses.values():
            all_recommendations.extend(status.recommendations)
            for issue in status.issues:
                if 'stale' in issue.lower() or 'old' in issue.lower():
                    all_recommendations.append(f"Improve data freshness: {issue}")
                elif 'invalid' in issue.lower() or 'corrupted' in issue.lower():
                    all_recommendations.append(f"Fix data accuracy: {issue}")
                elif 'missing' in issue.lower():
                    all_recommendations.append(f"Improve data completeness: {issue}")
        
        return list(set(all_recommendations))  # Remove duplicates

# Global instance
data_quality_checker = DataQualityChecker()

def get_data_quality_checker() -> DataQualityChecker:
    """Get global data quality checker instance"""
    return data_quality_checker

if __name__ == "__main__":
    # Test the data quality checker
    checker = DataQualityChecker()
    
    print("📊 Data Quality Checker Test")
    print("=" * 50)
    
    # Check individual data sources
    for data_type in ['price_data', 'sentiment_data', 'whale_data', 'chart_data']:
        print(f"\nChecking {data_type}...")
        if data_type == 'price_data':
            status = checker.check_price_data_quality()
        elif data_type == 'sentiment_data':
            status = checker.check_sentiment_data_quality()
        elif data_type == 'whale_data':
            status = checker.check_whale_data_quality()
        else:
            status = checker.check_chart_data_quality()
        
        print(f"  Status: {status.status}")
        print(f"  Freshness: {status.freshness_score:.2f}")
        print(f"  Accuracy: {status.accuracy_score:.2f}")
        print(f"  Completeness: {status.completeness_score:.2f}")
        print(f"  Issues: {len(status.issues)}")
        for issue in status.issues:
            print(f"    - {issue}")
    
    # Get summary
    summary = checker.get_data_quality_summary()
    print(f"\nSummary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Get recommendations
    recommendations = checker.get_data_quality_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
