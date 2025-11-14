"""
Interactive test script for manual agent testing and scenario simulation
"""

import os
import sys
import time
from typing import Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from test.agents.test_helpers import PortfolioStateSimulator, TestValidator, create_test_token_addresses
from test.agents.test_rebalancing_scenarios import TestRebalancingScenarios
from test.agents.test_harvesting_scenarios import TestHarvestingScenarios
from test.agents.test_agent_integration import TestAgentIntegration
from src.agents.rebalancing_agent import RebalancingAgent
from src.agents.harvesting_agent import HarvestingAgent
from src.config import SOL_ADDRESS, USDC_ADDRESS

class InteractiveAgentTester:
    """Interactive command-line tool for manual agent testing"""
    
    def __init__(self):
        self.simulator = PortfolioStateSimulator()
        self.validator = TestValidator()
        self.rebalancing_agent = None
        self.harvesting_agent = None
        self.setup_mocked_agents()
    
    def setup_mocked_agents(self):
        """Setup agents with mocked services"""
        mock_price_service, mock_api_manager, mock_data_coordinator = self.simulator.create_mock_services()
        
        # Create agents with mocked services
        from unittest.mock import patch
        
        with patch('src.agents.rebalancing_agent.get_optimized_price_service', return_value=mock_price_service), \
             patch('src.agents.rebalancing_agent.get_shared_api_manager', return_value=mock_api_manager), \
             patch('src.agents.rebalancing_agent.get_shared_data_coordinator', return_value=mock_data_coordinator), \
             patch('src.agents.harvesting_agent.get_optimized_price_service', return_value=mock_price_service), \
             patch('src.agents.harvesting_agent.get_shared_api_manager', return_value=mock_api_manager), \
             patch('src.agents.harvesting_agent.get_shared_data_coordinator', return_value=mock_data_coordinator):
            
            self.rebalancing_agent = RebalancingAgent()
            self.harvesting_agent = HarvestingAgent()
    
    def display_menu(self):
        """Display the main menu"""
        print("\n" + "="*60)
        print("🤖 INTERACTIVE AGENT TESTING TOOL")
        print("="*60)
        print("1. Reset portfolio to clean state")
        print("2. Set custom portfolio allocation")
        print("3. Test rebalancing agent")
        print("4. Test harvesting agent")
        print("5. Run specific scenario by name")
        print("6. View current portfolio state")
        print("7. Run all tests")
        print("8. Simulate portfolio changes")
        print("9. Test agent coordination")
        print("0. Exit")
        print("="*60)
    
    def reset_portfolio(self):
        """Reset portfolio to clean state"""
        print("\n🔄 Resetting portfolio to clean state (100% SOL)...")
        self.simulator.reset_to_clean_state()
        state = self.simulator.get_current_state()
        print(f"✅ Portfolio reset complete:")
        print(f"   SOL: ${state['sol_usd']:.2f} ({state['sol_pct']:.1%})")
        print(f"   USDC: ${state['usdc_usd']:.2f} ({state['usdc_pct']:.1%})")
        print(f"   Positions: ${state['positions_usd']:.2f} ({state['positions_pct']:.1%})")
        print(f"   Total: ${state['total_value']:.2f}")
    
    def set_custom_allocation(self):
        """Set custom portfolio allocation"""
        print("\n📊 Set Custom Portfolio Allocation")
        print("-" * 40)
        
        try:
            sol_usd = float(input("Enter SOL value in USD: "))
            usdc_usd = float(input("Enter USDC value in USD: "))
            positions_usd = float(input("Enter positions value in USD: "))
            
            # Ask if user wants specific positions
            create_positions = input("Create specific positions? (y/n): ").lower() == 'y'
            positions = None
            
            if create_positions:
                num_positions = int(input("Number of positions to create: "))
                positions = {}
                for i in range(num_positions):
                    token_address = input(f"Token address {i+1}: ")
                    value = float(input(f"Value in USD for {token_address[:8]}...: "))
                    positions[token_address] = value
            
            self.simulator.set_portfolio_state(sol_usd, usdc_usd, positions_usd, positions)
            
            state = self.simulator.get_current_state()
            print(f"\n✅ Portfolio updated:")
            print(f"   SOL: ${state['sol_usd']:.2f} ({state['sol_pct']:.1%})")
            print(f"   USDC: ${state['usdc_usd']:.2f} ({state['usdc_pct']:.1%})")
            print(f"   Positions: ${state['positions_usd']:.2f} ({state['positions_pct']:.1%})")
            print(f"   Total: ${state['total_value']:.2f}")
            
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_rebalancing_agent(self):
        """Test rebalancing agent"""
        print("\n⚖️ Testing Rebalancing Agent")
        print("-" * 40)
        
        try:
            actions = self.rebalancing_agent.check_portfolio_allocation()
            
            if actions:
                print("🔄 Rebalancing actions needed:")
                for i, action in enumerate(actions, 1):
                    print(f"   {i}. {action}")
                
                # Ask if user wants to execute
                execute = input("\nExecute rebalancing? (y/n): ").lower() == 'y'
                if execute:
                    print("🔄 Executing rebalancing...")
                    # Note: In real implementation, this would execute the trades
                    print("✅ Rebalancing executed (simulated)")
            else:
                print("✅ No rebalancing actions needed")
                
        except Exception as e:
            print(f"❌ Error testing rebalancing agent: {e}")
    
    def test_harvesting_agent(self):
        """Test harvesting agent"""
        print("\n🌾 Testing Harvesting Agent")
        print("-" * 40)
        
        try:
            # Test dust conversion
            print("🔄 Testing dust conversion...")
            dust_success = self.harvesting_agent.auto_convert_dust_to_sol()
            print(f"Dust conversion: {'✅ Success' if dust_success else '❌ Failed'}")
            
            # Test realized gains (simulate 5% gain)
            print("\n🔄 Testing realized gains harvesting...")
            from test.agents.test_harvesting_scenarios import MockSnapshot
            
            current_state = self.simulator.get_current_state()
            previous_snapshot = MockSnapshot(current_state['total_value'])
            
            # Simulate 5% gain
            self.simulator.simulate_portfolio_gains(5.0)
            new_state = self.simulator.get_current_state()
            current_snapshot = MockSnapshot(new_state['total_value'])
            
            self.harvesting_agent._handle_realized_gains(current_snapshot, previous_snapshot)
            
            print(f"Realized gains total: ${self.harvesting_agent.realized_gains_total:.2f}")
            print(f"External transfers: {len(self.harvesting_agent.external_wallet_transfers)}")
            
            if self.harvesting_agent.external_wallet_transfers:
                print("📤 External wallet transfers:")
                for i, transfer in enumerate(self.harvesting_agent.external_wallet_transfers, 1):
                    print(f"   {i}. {transfer['sol_amount']:.6f} SOL to {transfer['wallet_address'][:8]}... ({transfer['status']})")
            
        except Exception as e:
            print(f"❌ Error testing harvesting agent: {e}")
    
    def run_specific_scenario(self):
        """Run specific scenario by name"""
        print("\n🎯 Run Specific Scenario")
        print("-" * 40)
        print("Available scenarios:")
        print("1. Startup Rebalancing (100% SOL)")
        print("2. USDC Depletion Crisis")
        print("3. SOL Critical Low")
        print("4. Dust Conversion")
        print("5. Realized Gains Harvesting")
        print("6. Fresh Start Complete Flow")
        
        try:
            choice = input("\nSelect scenario (1-6): ")
            
            if choice == "1":
                self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)
                print("✅ Set portfolio to 100% SOL")
                self.test_rebalancing_agent()
            elif choice == "2":
                self.simulator.set_portfolio_state(100.0, 50.0, 850.0)
                print("✅ Set portfolio to USDC depletion crisis")
                self.test_rebalancing_agent()
            elif choice == "3":
                self.simulator.set_portfolio_state(30.0, 600.0, 370.0)
                print("✅ Set portfolio to SOL critical low")
                self.test_rebalancing_agent()
            elif choice == "4":
                dust_tokens = create_test_token_addresses(3)
                dust_values = [0.50, 0.75, 1.00]
                self.simulator.set_portfolio_state(100.0, 100.0, 0.0)
                self.simulator.create_dust_positions(dust_tokens, dust_values)
                print("✅ Created dust positions")
                self.test_harvesting_agent()
            elif choice == "5":
                self.simulator.set_portfolio_state(100.0, 200.0, 700.0)
                print("✅ Set portfolio for realized gains test")
                self.test_harvesting_agent()
            elif choice == "6":
                print("✅ Running fresh start complete flow...")
                self.run_fresh_start_flow()
            else:
                print("❌ Invalid choice")
                
        except Exception as e:
            print(f"❌ Error running scenario: {e}")
    
    def run_fresh_start_flow(self):
        """Run the complete fresh start flow"""
        print("\n🚀 Fresh Start Complete Flow")
        print("-" * 40)
        
        # Step 1: Start with 100% SOL
        print("1. Starting with 100% SOL portfolio...")
        self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)
        self.view_portfolio_state()
        
        # Step 2: Run rebalancing
        print("\n2. Running rebalancing agent...")
        self.test_rebalancing_agent()
        
        # Step 3: Simulate rebalancing execution
        print("\n3. Simulating rebalancing execution...")
        self.simulator.set_portfolio_state(100.0, 900.0, 0.0)
        self.view_portfolio_state()
        
        # Step 4: Add copybot positions
        print("\n4. Adding copybot positions...")
        copybot_positions = {create_test_token_addresses(1)[0]: 300.0}
        self.simulator.set_portfolio_state(100.0, 600.0, 300.0, copybot_positions)
        self.view_portfolio_state()
        
        # Step 5: Test harvesting (no gains yet)
        print("\n5. Testing harvesting agent (no gains)...")
        self.test_harvesting_agent()
        
        # Step 6: Simulate gains
        print("\n6. Simulating 5% portfolio gains...")
        self.simulator.simulate_portfolio_gains(5.0)
        self.view_portfolio_state()
        
        # Step 7: Test harvesting with gains
        print("\n7. Testing harvesting agent with gains...")
        self.test_harvesting_agent()
        
        print("\n✅ Fresh start flow completed!")
    
    def view_portfolio_state(self):
        """View current portfolio state"""
        state = self.simulator.get_current_state()
        print(f"\n📊 Current Portfolio State:")
        print(f"   SOL: ${state['sol_usd']:.2f} ({state['sol_pct']:.1%})")
        print(f"   USDC: ${state['usdc_usd']:.2f} ({state['usdc_pct']:.1%})")
        print(f"   Positions: ${state['positions_usd']:.2f} ({state['positions_pct']:.1%})")
        print(f"   Total: ${state['total_value']:.2f}")
        
        if state['positions']:
            print(f"   Individual positions:")
            for token, value in state['positions'].items():
                print(f"     {token[:8]}...: ${value:.2f}")
    
    def simulate_portfolio_changes(self):
        """Simulate portfolio changes"""
        print("\n📈 Simulate Portfolio Changes")
        print("-" * 40)
        print("1. Simulate gains (percentage)")
        print("2. Add dust positions")
        print("3. Add specific position")
        print("4. Remove position")
        
        try:
            choice = input("Select option (1-4): ")
            
            if choice == "1":
                percentage = float(input("Enter gain percentage: "))
                self.simulator.simulate_portfolio_gains(percentage)
                print(f"✅ Simulated {percentage}% portfolio gains")
                self.view_portfolio_state()
            elif choice == "2":
                num_dust = int(input("Number of dust positions: "))
                dust_tokens = create_test_token_addresses(num_dust)
                dust_values = []
                for i in range(num_dust):
                    value = float(input(f"Dust value {i+1} (USD): "))
                    dust_values.append(value)
                self.simulator.create_dust_positions(dust_tokens, dust_values)
                print("✅ Added dust positions")
                self.view_portfolio_state()
            elif choice == "3":
                token_address = input("Token address: ")
                value = float(input("Value in USD: "))
                positions = self.simulator.get_current_state()['positions']
                positions[token_address] = value
                self.simulator.set_portfolio_state(
                    self.simulator.get_current_state()['sol_usd'],
                    self.simulator.get_current_state()['usdc_usd'],
                    self.simulator.get_current_state()['positions_usd'],
                    positions
                )
                print("✅ Added position")
                self.view_portfolio_state()
            elif choice == "4":
                self.view_portfolio_state()
                token_address = input("Token address to remove: ")
                positions = self.simulator.get_current_state()['positions']
                if token_address in positions:
                    del positions[token_address]
                    self.simulator.set_portfolio_state(
                        self.simulator.get_current_state()['sol_usd'],
                        self.simulator.get_current_state()['usdc_usd'],
                        self.simulator.get_current_state()['positions_usd'],
                        positions
                    )
                    print("✅ Removed position")
                else:
                    print("❌ Position not found")
            else:
                print("❌ Invalid choice")
                
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def test_agent_coordination(self):
        """Test agent coordination"""
        print("\n🤝 Testing Agent Coordination")
        print("-" * 40)
        
        # Set up scenario that needs both agents
        self.simulator.set_portfolio_state(1000.0, 0.0, 0.0)  # 100% SOL
        print("Set portfolio to 100% SOL (needs rebalancing)")
        
        # Test rebalancing first
        print("\n1. Testing rebalancing agent...")
        self.test_rebalancing_agent()
        
        # Simulate rebalancing execution
        self.simulator.set_portfolio_state(100.0, 900.0, 0.0)
        print("Simulated rebalancing execution")
        
        # Add positions and simulate gains
        copybot_positions = {create_test_token_addresses(1)[0]: 300.0}
        self.simulator.set_portfolio_state(100.0, 600.0, 300.0, copybot_positions)
        self.simulator.simulate_portfolio_gains(5.0)
        print("Added positions and simulated 5% gains")
        
        # Test harvesting
        print("\n2. Testing harvesting agent...")
        self.test_harvesting_agent()
        
        print("\n✅ Agent coordination test completed!")
    
    def run_all_tests(self):
        """Run all automated tests"""
        print("\n🧪 Running All Automated Tests")
        print("=" * 50)
        
        all_results = []
        
        # Run rebalancing tests
        print("\n⚖️ Running Rebalancing Agent Tests...")
        rebalancing_tests = TestRebalancingScenarios()
        rebalancing_results = rebalancing_tests.run_all_tests()
        all_results.extend(rebalancing_results)
        
        # Run harvesting tests
        print("\n🌾 Running Harvesting Agent Tests...")
        harvesting_tests = TestHarvestingScenarios()
        harvesting_results = harvesting_tests.run_all_tests()
        all_results.extend(harvesting_results)
        
        # Run integration tests
        print("\n🤝 Running Integration Tests...")
        integration_tests = TestAgentIntegration()
        integration_results = integration_tests.run_all_tests()
        all_results.extend(integration_results)
        
        # Generate final report
        print("\n📊 FINAL TEST REPORT")
        print("=" * 50)
        report = self.validator.generate_test_report(all_results)
        print(report)
        
        return all_results
    
    def run(self):
        """Main interactive loop"""
        print("🚀 Starting Interactive Agent Testing Tool...")
        
        while True:
            self.display_menu()
            
            try:
                choice = input("\nSelect option (0-9): ").strip()
                
                if choice == "0":
                    print("👋 Goodbye!")
                    break
                elif choice == "1":
                    self.reset_portfolio()
                elif choice == "2":
                    self.set_custom_allocation()
                elif choice == "3":
                    self.test_rebalancing_agent()
                elif choice == "4":
                    self.test_harvesting_agent()
                elif choice == "5":
                    self.run_specific_scenario()
                elif choice == "6":
                    self.view_portfolio_state()
                elif choice == "7":
                    self.run_all_tests()
                elif choice == "8":
                    self.simulate_portfolio_changes()
                elif choice == "9":
                    self.test_agent_coordination()
                else:
                    print("❌ Invalid choice. Please select 0-9.")
                
                input("\nPress Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter to continue...")


if __name__ == "__main__":
    tester = InteractiveAgentTester()
    tester.run()
