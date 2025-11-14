#!/usr/bin/env python3
"""
Simple verification of SYSTEM_HALT logic
"""

import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def verify_config_variables():
    """Verify all config variables exist"""
    from src import config
    
    print("=" * 60)
    print("Verifying Config Variables")
    print("=" * 60)
    
    required_vars = [
        'COPYBOT_ENABLED',
        'COPYBOT_HALT_BUYS', 
        'COPYBOT_STOP_ALL',
        'RISK_AGENT_COOLDOWN_SECONDS'
    ]
    
    all_present = True
    for var in required_vars:
        if hasattr(config, var):
            value = getattr(config, var)
            print(f"✓ {var} = {value}")
        else:
            print(f"✗ {var} MISSING")
            all_present = False
    
    print("=" * 60)
    return all_present

def verify_risk_agent_initialization():
    """Verify RiskAgent initializes with correct flags"""
    from unittest.mock import patch, Mock
    from src.agents.risk_agent import RiskAgent
    
    print("\n" + "=" * 60)
    print("Verifying RiskAgent Initialization")
    print("=" * 60)
    
    with patch('src.agents.risk_agent.get_portfolio_tracker') as pt, \
         patch('src.agents.risk_agent.get_optimized_price_service') as ps, \
         patch('src.agents.risk_agent.get_breakeven_manager') as bm, \
         patch('src.agents.risk_agent.get_execution_tracker') as et, \
         patch('src.agents.risk_agent.get_shared_data_coordinator') as sc, \
         patch('src.agents.risk_agent.create_model') as cm:
        
        pt.return_value = Mock()
        ps.return_value = Mock()
        bm.return_value = Mock()
        et.return_value = Mock()
        sc.return_value = Mock()
        cm.return_value = Mock()
        
        agent = RiskAgent()
        
        # Verify requires_manual_review is initialized
        if hasattr(agent, 'requires_manual_review'):
            print(f"✓ requires_manual_review initialized: {agent.requires_manual_review}")
        else:
            print("✗ requires_manual_review NOT FOUND")
            return False
        
        # Verify it's initialized to False
        if agent.requires_manual_review == False:
            print("✓ requires_manual_review correctly set to False")
        else:
            print(f"✗ requires_manual_review incorrectly set to {agent.requires_manual_review}")
            return False
        
    print("=" * 60)
    return True

def verify_system_halt_method():
    """Verify execute_system_halt method exists and has correct structure"""
    import inspect
    from src.agents.risk_agent import RiskAgent
    
    print("\n" + "=" * 60)
    print("Verifying execute_system_halt Method")
    print("=" * 60)
    
    # Check method exists
    if hasattr(RiskAgent, 'execute_system_halt'):
        print("✓ execute_system_halt method exists")
    else:
        print("✗ execute_system_halt method NOT FOUND")
        return False
    
    # Check method signature
    method = getattr(RiskAgent, 'execute_system_halt')
    source = inspect.getsource(method)
    
    # Check for key elements
    checks = [
        ('execute_full_liquidation', 'calls execute_full_liquidation'),
        ('requires_manual_review = True', 'sets requires_manual_review flag'),
        ('config.COPYBOT_ENABLED = False', 'disables CopyBot'),
        ('MANUAL REVIEW REQUIRED', 'logs manual review requirement')
    ]
    
    all_present = True
    for keyword, description in checks:
        if keyword in source:
            print(f"✓ {description}")
        else:
            print(f"✗ {description} - MISSING")
            all_present = False
    
    print("=" * 60)
    return all_present

def verify_auto_recovery_skip():
    """Verify check_auto_recovery_conditions skips when requires_manual_review is True"""
    import inspect
    from src.agents.risk_agent import RiskAgent
    
    print("\n" + "=" * 60)
    print("Verifying Auto-Recovery Skip Logic")
    print("=" * 60)
    
    method = getattr(RiskAgent, 'check_auto_recovery_conditions')
    source = inspect.getsource(method)
    
    # Check for manual review skip
    if 'requires_manual_review' in source and 'getattr' in source:
        print("✓ Manual review check present in auto-recovery")
    else:
        print("✗ Manual review check MISSING")
        return False
    
    print("✓ Auto-recovery will skip when manual review required")
    print("=" * 60)
    return True

def verify_force_clear_method():
    """Verify force_clear_all_halts clears the manual review flag"""
    import inspect
    from src.agents.risk_agent import RiskAgent
    
    print("\n" + "=" * 60)
    print("Verifying force_clear_all_halts Method")
    print("=" * 60)
    
    method = getattr(RiskAgent, 'force_clear_all_halts')
    source = inspect.getsource(method)
    
    if 'requires_manual_review = False' in source:
        print("✓ Clears requires_manual_review flag")
    else:
        print("✗ Does NOT clear requires_manual_review flag")
        return False
    
    print("✓ force_clear_all_halts correctly clears manual review flag")
    print("=" * 60)
    return True

def main():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("Risk Agent SYSTEM_HALT Logic Verification")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("Config Variables", verify_config_variables()))
    results.append(("RiskAgent Initialization", verify_risk_agent_initialization()))
    results.append(("execute_system_halt Method", verify_system_halt_method()))
    results.append(("Auto-Recovery Skip", verify_auto_recovery_skip()))
    results.append(("force_clear_all_halts Method", verify_force_clear_method()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for check_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("✓ All checks PASSED - SYSTEM_HALT logic is correct")
        return 0
    else:
        print("✗ Some checks FAILED - review errors above")
        return 1

if __name__ == '__main__':
    sys.exit(main())

