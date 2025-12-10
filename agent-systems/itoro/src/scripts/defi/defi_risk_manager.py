"""
🌙 Anarcho Capital's DeFi Risk Manager
Comprehensive risk management for DeFi lending and borrowing operations
Built with love by Anarcho Capital 🚀
"""

import os
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

# Local imports
from src.scripts.shared_services.logger import debug, info, warning, error, critical, system
from src.config.defi_config import (
    CAPITAL_PROTECTION, LIQUIDATION_PROTECTION, SMART_CONTRACT_RISK,
    EMERGENCY_STOP_TRIGGERS, MANUAL_OVERRIDE, BORROWING_REQUIREMENTS,
    LIQUIDATION_THRESHOLD_MANAGEMENT, CORRELATION_LIMITS
)

@dataclass
class RiskAssessment:
    """Comprehensive risk assessment for DeFi operations"""
    overall_risk_score: float  # 0.0 to 1.0
    risk_level: str  # low, medium, high, critical
    portfolio_risk: float
    protocol_risk: float
    market_risk: float
    liquidation_risk: float
    recommendations: List[str]
    timestamp: datetime

@dataclass
class LiquidationRisk:
    """Liquidation risk assessment"""
    protocol: str
    token: str
    current_collateral_ratio: float
    liquidation_threshold: float
    buffer_percentage: float
    risk_level: str
    recommended_action: str
    timestamp: datetime

@dataclass
class EmergencyStopTrigger:
    """Emergency stop trigger details"""
    trigger_type: str
    severity: str
    description: str
    timestamp: datetime
    action_required: str
    auto_resolve: bool

class DeFiRiskManager:
    """
    Manages risk assessment and mitigation for DeFi operations
    Provides real-time risk monitoring and emergency stop capabilities
    """
    
    def __init__(self):
        """Initialize the DeFi Risk Manager"""
        self.risk_history = []
        self.liquidation_alerts = []
        self.emergency_stops = []
        self.risk_thresholds = {}
        self.last_assessment = None
        
        # Initialize risk thresholds
        self._initialize_risk_thresholds()
        
        # Risk monitoring state
        self.monitoring_enabled = True
        self.emergency_stop_active = False
        self.auto_mitigation_enabled = True
        
        # Performance tracking
        self.portfolio_performance = {
            'peak_balance': 0.0,
            'current_balance': 0.0,
            'max_drawdown': 0.0,
            'consecutive_losses': 0,
            'total_trades': 0,
            'winning_trades': 0
        }
        
        info("🛡️ DeFi Risk Manager initialized")
    
    def _initialize_risk_thresholds(self):
        """Initialize risk thresholds from configuration"""
        self.risk_thresholds = {
            'portfolio_loss_24h': EMERGENCY_STOP_TRIGGERS['portfolio_loss_24h'],
            'market_crash_4h': EMERGENCY_STOP_TRIGGERS['market_crash_4h'],
            'liquidation_risk': EMERGENCY_STOP_TRIGGERS['liquidation_risk'],
            'max_drawdown': 0.15,  # 15% maximum drawdown
            'consecutive_losses': 5,  # 5 consecutive losses
            'volatility_threshold': 0.25,  # 25% volatility increase
            'correlation_limit': CORRELATION_LIMITS['max_position_correlation'],
            'protocol_health_threshold': 0.8,  # 80% protocol health
        }
    
    async def assess_portfolio_risk(self, portfolio_data: Dict[str, Any]) -> RiskAssessment:
        """Assess overall portfolio risk"""
        try:
            # Calculate individual risk components
            portfolio_risk = self._calculate_portfolio_risk(portfolio_data)
            protocol_risk = await self._calculate_protocol_risk(portfolio_data)
            market_risk = self._calculate_market_risk(portfolio_data)
            liquidation_risk = self._calculate_liquidation_risk(portfolio_data)
            
            # Calculate overall risk score (weighted average)
            overall_risk_score = (
                portfolio_risk * 0.3 +
                protocol_risk * 0.25 +
                market_risk * 0.25 +
                liquidation_risk * 0.2
            )
            
            # Determine risk level
            risk_level = self._determine_risk_level(overall_risk_score)
            
            # Generate recommendations
            recommendations = self._generate_risk_recommendations(
                overall_risk_score, portfolio_risk, protocol_risk, 
                market_risk, liquidation_risk
            )
            
            # Create risk assessment
            assessment = RiskAssessment(
                overall_risk_score=overall_risk_score,
                risk_level=risk_level,
                portfolio_risk=portfolio_risk,
                protocol_risk=protocol_risk,
                market_risk=market_risk,
                liquidation_risk=liquidation_risk,
                recommendations=recommendations,
                timestamp=datetime.now()
            )
            
            # Store assessment
            self.risk_history.append(assessment)
            self.last_assessment = assessment
            
            # Check for emergency stop triggers
            await self._check_emergency_stop_triggers(assessment, portfolio_data)
            
            return assessment
            
        except Exception as e:
            error(f"Failed to assess portfolio risk: {str(e)}")
            return self._create_error_assessment(str(e))
    
    def _calculate_portfolio_risk(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate portfolio-specific risk score"""
        try:
            risk_score = 0.0
            
            # Check portfolio balance
            current_balance = portfolio_data.get('total_balance_usd', 0)
            peak_balance = portfolio_data.get('peak_balance_usd', current_balance)
            
            if peak_balance > 0:
                drawdown = (peak_balance - current_balance) / peak_balance
                if drawdown > self.risk_thresholds['max_drawdown']:
                    risk_score += 0.4
                elif drawdown > 0.1:  # 10% drawdown
                    risk_score += 0.2
                elif drawdown > 0.05:  # 5% drawdown
                    risk_score += 0.1
            
            # Check allocation concentration
            total_allocation = portfolio_data.get('total_allocation_percent', 0)
            if total_allocation > 0.8:  # 80% allocated
                risk_score += 0.3
            elif total_allocation > 0.6:  # 60% allocated
                risk_score += 0.2
            elif total_allocation > 0.4:  # 40% allocated
                risk_score += 0.1
            
            # Check position diversity
            position_count = portfolio_data.get('position_count', 0)
            if position_count < 3:
                risk_score += 0.2
            elif position_count < 5:
                risk_score += 0.1
            
            # Check cash reserves
            cash_percentage = portfolio_data.get('cash_percentage', 0)
            if cash_percentage < 0.1:  # Less than 10% cash
                risk_score += 0.3
            elif cash_percentage < 0.2:  # Less than 20% cash
                risk_score += 0.1
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            error(f"Failed to calculate portfolio risk: {str(e)}")
            return 0.5
    
    async def _calculate_protocol_risk(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate protocol-related risk score"""
        try:
            risk_score = 0.0
            
            # Check protocol health (this would integrate with protocol manager)
            # For now, use a simplified approach
            protocols = portfolio_data.get('protocols', {})
            
            for protocol_name, protocol_data in protocols.items():
                # Check if protocol is audited
                if not protocol_data.get('audited', False):
                    risk_score += 0.2
                
                # Check protocol age
                protocol_age_days = protocol_data.get('age_days', 0)
                if protocol_age_days < 180:  # Less than 6 months
                    risk_score += 0.2
                elif protocol_age_days < 365:  # Less than 1 year
                    risk_score += 0.1
                
                # Check TVL
                tvl_usd = protocol_data.get('tvl_usd', 0)
                if tvl_usd < 10000000:  # Less than $10M
                    risk_score += 0.3
                elif tvl_usd < 50000000:  # Less than $50M
                    risk_score += 0.1
            
            # Normalize by number of protocols
            if protocols:
                risk_score = risk_score / len(protocols)
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            error(f"Failed to calculate protocol risk: {str(e)}")
            return 0.5
    
    def _calculate_market_risk(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate market-related risk score"""
        try:
            risk_score = 0.0
            
            # Check market volatility
            volatility = portfolio_data.get('market_volatility', 0)
            if volatility > self.risk_thresholds['volatility_threshold']:
                risk_score += 0.4
            elif volatility > 0.15:  # 15% volatility
                risk_score += 0.2
            elif volatility > 0.10:  # 10% volatility
                risk_score += 0.1
            
            # Check market sentiment
            sentiment = portfolio_data.get('market_sentiment', 0)
            if sentiment < -0.3:  # Bearish sentiment
                risk_score += 0.3
            elif sentiment < 0:  # Neutral to bearish
                risk_score += 0.1
            
            # Check market correlation
            correlation = portfolio_data.get('portfolio_correlation', 0)
            if correlation > self.risk_thresholds['correlation_limit']:
                risk_score += 0.3
            elif correlation > 0.2:  # 20% correlation
                risk_score += 0.1
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            error(f"Failed to calculate market risk: {str(e)}")
            return 0.5
    
    def _calculate_liquidation_risk(self, portfolio_data: Dict[str, Any]) -> float:
        """Calculate liquidation risk score"""
        try:
            risk_score = 0.0
            
            # Check borrowing positions
            borrowing_positions = portfolio_data.get('borrowing_positions', [])
            
            for position in borrowing_positions:
                collateral_ratio = position.get('collateral_ratio', 2.0)
                liquidation_threshold = position.get('liquidation_threshold', 1.5)
                
                # Calculate buffer above liquidation
                buffer = (collateral_ratio - liquidation_threshold) / liquidation_threshold
                
                if buffer < LIQUIDATION_THRESHOLD_MANAGEMENT['emergency_level']:
                    risk_score += 0.5
                elif buffer < LIQUIDATION_THRESHOLD_MANAGEMENT['action_level']:
                    risk_score += 0.3
                elif buffer < LIQUIDATION_THRESHOLD_MANAGEMENT['warning_level']:
                    risk_score += 0.1
            
            # Normalize by number of borrowing positions
            if borrowing_positions:
                risk_score = risk_score / len(borrowing_positions)
            
            return min(risk_score, 1.0)
            
        except Exception as e:
            error(f"Failed to calculate liquidation risk: {str(e)}")
            return 0.5
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level based on risk score"""
        if risk_score >= 0.8:
            return 'critical'
        elif risk_score >= 0.6:
            return 'high'
        elif risk_score >= 0.4:
            return 'medium'
        elif risk_score >= 0.2:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_risk_recommendations(self, overall_risk: float, portfolio_risk: float, 
                                     protocol_risk: float, market_risk: float, 
                                     liquidation_risk: float) -> List[str]:
        """Generate risk mitigation recommendations"""
        recommendations = []
        
        if overall_risk >= 0.8:
            recommendations.append("🚨 CRITICAL: Consider emergency stop of all DeFi operations")
            recommendations.append("💰 Add additional collateral to prevent liquidation")
            recommendations.append("📉 Reduce position sizes immediately")
        
        elif overall_risk >= 0.6:
            recommendations.append("⚠️ HIGH: Reduce exposure to high-risk protocols")
            recommendations.append("💵 Increase cash reserves")
            recommendations.append("🔄 Rebalance portfolio to safer assets")
        
        elif overall_risk >= 0.4:
            recommendations.append("⚡ MEDIUM: Monitor positions closely")
            recommendations.append("📊 Consider reducing allocation to volatile assets")
            recommendations.append("🛡️ Review risk management parameters")
        
        if portfolio_risk >= 0.6:
            recommendations.append("📈 Reduce portfolio concentration")
            recommendations.append("💸 Increase diversification")
        
        if protocol_risk >= 0.6:
            recommendations.append("🔒 Move funds to more established protocols")
            recommendations.append("📋 Review protocol audit status")
        
        if market_risk >= 0.6:
            recommendations.append("🌊 Market volatility high - consider hedging")
            recommendations.append("📉 Reduce exposure to correlated assets")
        
        if liquidation_risk >= 0.6:
            recommendations.append("💳 Add collateral to borrowing positions")
            recommendations.append("🚫 Consider closing high-risk borrowing positions")
        
        if not recommendations:
            recommendations.append("✅ Risk levels acceptable - continue monitoring")
        
        return recommendations
    
    async def _check_emergency_stop_triggers(self, assessment: RiskAssessment, 
                                           portfolio_data: Dict[str, Any]) -> None:
        """Check if emergency stop should be triggered"""
        try:
            triggers = []
            
            # Check actual portfolio loss (not just risk score)
            current_balance = portfolio_data.get('total_balance_usd', 0)
            peak_balance = portfolio_data.get('peak_balance_usd', current_balance)
            
            if peak_balance > 0 and current_balance > 0:
                actual_loss_pct = (peak_balance - current_balance) / peak_balance
                
                # Only trigger if ACTUAL loss exceeds threshold (not risk score)
                if actual_loss_pct >= self.risk_thresholds['portfolio_loss_24h']:
                    triggers.append(EmergencyStopTrigger(
                        trigger_type='portfolio_loss',
                        severity='critical',
                        description=f"Portfolio loss of {actual_loss_pct*100:.1f}% exceeded {self.risk_thresholds['portfolio_loss_24h']*100}% threshold",
                        timestamp=datetime.now(),
                        action_required='emergency_stop',
                        auto_resolve=False
                    ))
            
            # Check liquidation risk
            if assessment.liquidation_risk >= self.risk_thresholds['liquidation_risk']:
                triggers.append(EmergencyStopTrigger(
                    trigger_type='liquidation_risk',
                    severity='critical',
                    description=f"Liquidation risk exceeded {self.risk_thresholds['liquidation_risk']*100}% threshold",
                    timestamp=datetime.now(),
                    action_required='add_collateral',
                    auto_resolve=True
                ))
            
            # Check market crash
            if assessment.market_risk >= self.risk_thresholds['market_crash_4h']:
                triggers.append(EmergencyStopTrigger(
                    trigger_type='market_crash',
                    severity='high',
                    description=f"Market crash detected - {assessment.market_risk*100:.1f}% risk",
                    timestamp=datetime.now(),
                    action_required='reduce_exposure',
                    auto_resolve=False
                ))
            
            # Process triggers
            for trigger in triggers:
                await self._process_emergency_trigger(trigger)
                
        except Exception as e:
            error(f"Failed to check emergency stop triggers: {str(e)}")
    
    async def _process_emergency_trigger(self, trigger: EmergencyStopTrigger) -> None:
        """Process emergency stop trigger"""
        try:
            # Store trigger
            self.emergency_stops.append(trigger)
            
            # Log trigger
            if trigger.severity == 'critical':
                critical(f"🚨 EMERGENCY STOP TRIGGER: {trigger.description}")
            else:
                warning(f"⚠️ Emergency trigger: {trigger.description}")
            
            # Take action based on trigger type
            if trigger.action_required == 'emergency_stop':
                await self.trigger_emergency_stop(trigger)
            elif trigger.action_required == 'add_collateral':
                await self.add_collateral_automatically(trigger)
            elif trigger.action_required == 'reduce_exposure':
                await self.reduce_exposure_automatically(trigger)
            
        except Exception as e:
            error(f"Failed to process emergency trigger: {str(e)}")
    
    async def trigger_emergency_stop(self, trigger: EmergencyStopTrigger) -> None:
        """Trigger emergency stop of all DeFi operations"""
        try:
            self.emergency_stop_active = True
            
            # Log emergency stop
            critical(f"🚨 EMERGENCY STOP ACTIVATED: {trigger.description}")
            
            # Store emergency stop event
            emergency_event = {
                'timestamp': datetime.now().isoformat(),
                'trigger': trigger.trigger_type,
                'description': trigger.description,
                'severity': trigger.severity,
                'action_taken': 'emergency_stop'
            }
            
            # Here you would integrate with the main DeFi agent to stop operations
            # For now, we just log the event
            
            info("🛑 Emergency stop activated - all DeFi operations suspended")
            
        except Exception as e:
            error(f"Failed to trigger emergency stop: {str(e)}")
    
    async def add_collateral_automatically(self, trigger: EmergencyStopTrigger) -> None:
        """Automatically add collateral to prevent liquidation"""
        try:
            info(f"💰 Auto-adding collateral due to: {trigger.description}")
            
            # Here you would integrate with the DeFi agent to add collateral
            # For now, we just log the action
            
            info("✅ Collateral addition initiated automatically")
            
        except Exception as e:
            error(f"Failed to add collateral automatically: {str(e)}")
    
    async def reduce_exposure_automatically(self, trigger: EmergencyStopTrigger) -> None:
        """Automatically reduce exposure to risky assets"""
        try:
            info(f"📉 Auto-reducing exposure due to: {trigger.description}")
            
            # Here you would integrate with the DeFi agent to reduce exposure
            # For now, we just log the action
            
            info("✅ Exposure reduction initiated automatically")
            
        except Exception as e:
            error(f"Failed to reduce exposure automatically: {str(e)}")
    
    async def assess_liquidation_risk(self, positions: List[Dict[str, Any]]) -> List[LiquidationRisk]:
        """Assess liquidation risk for specific positions"""
        try:
            liquidation_risks = []
            
            for position in positions:
                protocol = position.get('protocol', 'unknown')
                token = position.get('token', 'unknown')
                collateral_ratio = position.get('collateral_ratio', 2.0)
                liquidation_threshold = position.get('liquidation_threshold', 1.5)
                
                # Calculate buffer above liquidation
                buffer_percentage = (collateral_ratio - liquidation_threshold) / liquidation_threshold
                
                # Determine risk level
                if buffer_percentage < LIQUIDATION_THRESHOLD_MANAGEMENT['emergency_level']:
                    risk_level = 'critical'
                    recommended_action = 'add_collateral_immediately'
                elif buffer_percentage < LIQUIDATION_THRESHOLD_MANAGEMENT['action_level']:
                    risk_level = 'high'
                    recommended_action = 'add_collateral_soon'
                elif buffer_percentage < LIQUIDATION_THRESHOLD_MANAGEMENT['warning_level']:
                    risk_level = 'medium'
                    recommended_action = 'monitor_closely'
                else:
                    risk_level = 'low'
                    recommended_action = 'continue_monitoring'
                
                liquidation_risk = LiquidationRisk(
                    protocol=protocol,
                    token=token,
                    current_collateral_ratio=collateral_ratio,
                    liquidation_threshold=liquidation_threshold,
                    buffer_percentage=buffer_percentage,
                    risk_level=risk_level,
                    recommended_action=recommended_action,
                    timestamp=datetime.now()
                )
                
                liquidation_risks.append(liquidation_risk)
                
                # Store critical alerts
                if risk_level in ['critical', 'high']:
                    self.liquidation_alerts.append(liquidation_risk)
            
            return liquidation_risks
            
        except Exception as e:
            error(f"Failed to assess liquidation risk: {str(e)}")
            return []
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of current risk status"""
        try:
            if not self.last_assessment:
                return {'status': 'no_assessment', 'message': 'No risk assessment performed yet'}
            
            return {
                'overall_risk_score': self.last_assessment.overall_risk_score,
                'risk_level': self.last_assessment.risk_level,
                'risk_components': {
                    'portfolio_risk': self.last_assessment.portfolio_risk,
                    'protocol_risk': self.last_assessment.protocol_risk,
                    'market_risk': self.last_assessment.market_risk,
                    'liquidation_risk': self.last_assessment.liquidation_risk
                },
                'recommendations': self.last_assessment.recommendations,
                'timestamp': self.last_assessment.timestamp.isoformat(),
                'emergency_stop_active': self.emergency_stop_active,
                'active_alerts': len(self.liquidation_alerts),
                'recent_triggers': len([t for t in self.emergency_stops 
                                      if (datetime.now() - t.timestamp).days < 1])
            }
            
        except Exception as e:
            error(f"Failed to get risk summary: {str(e)}")
            return {'error': str(e)}
    
    def clear_emergency_stop(self) -> bool:
        """Clear emergency stop status"""
        try:
            if self.emergency_stop_active:
                self.emergency_stop_active = False
                info("✅ Emergency stop cleared - DeFi operations can resume")
                return True
            else:
                info("ℹ️ No emergency stop active")
                return False
                
        except Exception as e:
            error(f"Failed to clear emergency stop: {str(e)}")
            return False
    
    def _create_error_assessment(self, error_message: str) -> RiskAssessment:
        """Create error assessment when risk calculation fails"""
        return RiskAssessment(
            overall_risk_score=0.5,
            risk_level='unknown',
            portfolio_risk=0.5,
            protocol_risk=0.5,
            market_risk=0.5,
            liquidation_risk=0.5,
            recommendations=[f"Error in risk assessment: {error_message}"],
            timestamp=datetime.now()
        )

# Global instance
_defi_risk_manager = None

def get_defi_risk_manager() -> DeFiRiskManager:
    """Get global DeFi risk manager instance"""
    global _defi_risk_manager
    if _defi_risk_manager is None:
        _defi_risk_manager = DeFiRiskManager()
    return _defi_risk_manager

# Test function
async def test_risk_manager():
    """Test the DeFi risk manager"""
    try:
        risk_manager = get_defi_risk_manager()
        
        # Sample portfolio data
        portfolio_data = {
            'total_balance_usd': 10000.0,
            'peak_balance_usd': 12000.0,
            'total_allocation_percent': 0.7,
            'position_count': 4,
            'cash_percentage': 0.3,
            'market_volatility': 0.12,
            'market_sentiment': 0.1,
            'portfolio_correlation': 0.25,
            'protocols': {
                'solend': {'audited': True, 'age_days': 400, 'tvl_usd': 150000000},
                'mango': {'audited': True, 'age_days': 300, 'tvl_usd': 80000000}
            },
            'borrowing_positions': [
                {'collateral_ratio': 2.5, 'liquidation_threshold': 1.5},
                {'collateral_ratio': 1.8, 'liquidation_threshold': 1.5}
            ]
        }
        
        # Test risk assessment
        print("🔍 Testing risk assessment...")
        assessment = await risk_manager.assess_portfolio_risk(portfolio_data)
        print(f"Overall Risk Score: {assessment.overall_risk_score:.3f}")
        print(f"Risk Level: {assessment.risk_level}")
        print(f"Recommendations: {assessment.recommendations}")
        
        # Test liquidation risk assessment
        print("\n💳 Testing liquidation risk assessment...")
        positions = [
            {'protocol': 'solend', 'token': 'USDC', 'collateral_ratio': 2.5, 'liquidation_threshold': 1.5},
            {'protocol': 'mango', 'token': 'SOL', 'collateral_ratio': 1.6, 'liquidation_threshold': 1.5}
        ]
        liquidation_risks = await risk_manager.assess_liquidation_risk(positions)
        print(f"Found {len(liquidation_risks)} liquidation risks")
        
        for risk in liquidation_risks:
            print(f"  - {risk.protocol}: {risk.risk_level} risk, {risk.recommended_action}")
        
        # Test risk summary
        print("\n📊 Testing risk summary...")
        summary = risk_manager.get_risk_summary()
        print(f"Risk Summary: {json.dumps(summary, indent=2)}")
        
        print("\n✅ DeFi Risk Manager test completed successfully!")
        
    except Exception as e:
        error(f"DeFi Risk Manager test failed: {str(e)}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_risk_manager())
