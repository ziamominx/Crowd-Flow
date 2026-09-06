"""
PHASE 3: HEADLESS GLOBAL TRAINING MATRIX
Compiles 10,000s of simulations to finalize optimal weights before PMO deployment.
"""

import time
import math
import random
import torch
import os
from rl_agent import DeepRLRewardEngine, GlobalTrafficState
from graph_engine import CityGraphPhysics

print("--- 🧠 INITIALIZING PHASE 3 TRAINING MATRIX ---")

def compute_density(v): return float(round(min(v / 50.0, 1.0), 2))
def estimate_speed(v): return float(max(60.0 * math.exp(-0.05 * v), 5.0))
def compute_flow(v, s): return float(round(v * s, 1))

def reset_env():
    # Base Traffic Simulation Start
    state = {
        "silk_board": {"vehicles": random.randint(30, 60)},
        "madiwala": {"vehicles": random.randint(20, 50)},
        "koramangala": {"vehicles": random.randint(10, 40)}
    }
    for j, data in state.items():
        v = data["vehicles"]
        data["speed"] = estimate_speed(v)
        data["density"] = compute_density(v)
        data["flow"] = compute_flow(v, data["speed"])
    return state

def extract_state_object(state_dict) -> GlobalTrafficState:
    densities = [
        state_dict["silk_board"]["density"],
        state_dict["madiwala"]["density"],
        state_dict["koramangala"]["density"]
    ]
    flows = [
        state_dict["silk_board"]["flow"],
        state_dict["madiwala"]["flow"],
        state_dict["koramangala"]["flow"]
    ]
    return GlobalTrafficState(densities, flows)

def apply_action(state_dict, action, graph):
    # Action map: 0: Decrease, 1: Maintain, 2: Increase, 3: Force Flush
    green_seconds = 0
    if action == 2:   green_seconds = 45
    elif action == 3: green_seconds = 90
    elif action == 1: green_seconds = 30
    
    # Fast Dispatch specific to Silk Board target node in testing
    source = "silk_board"
    if green_seconds >= 30 and state_dict[source]["density"] > 0.1:
        if state_dict["madiwala"]["density"] <= 0.9:
            pushed = int(max(1, min(state_dict[source]["vehicles"], state_dict[source]["flow"] * 0.05)))
            # Suppress prints during headless training
            graph.dispatch_wave(source, pushed, state_dict[source]["speed"])
            state_dict[source]["vehicles"] -= pushed

def update_state(state_dict, arrivals):
    # Process physics
    for junction, incoming in arrivals.items():
        if incoming > 0:
            state_dict[junction]["vehicles"] += incoming
            
    # Simulate constant incoming traffic naturally hitting Bengaluru via real physics bounds
    state_dict["silk_board"]["vehicles"] += random.randint(2, 5)
    
    # Flush Koramangala dynamically out of system
    state_dict["koramangala"]["vehicles"] = max(0, state_dict["koramangala"]["vehicles"] - random.randint(4, 9))
    
    # Recompute dependencies
    for j, data in state_dict.items():
        v = data["vehicles"]
        data["speed"] = estimate_speed(v)
        data["density"] = compute_density(v)
        data["flow"] = compute_flow(v, data["speed"])

def run_matrix():
    agent = DeepRLRewardEngine()
    graph = CityGraphPhysics()
    
    episodes = 200 # Fast-tracked for immediate testing. Increase to 2000 for overnight.
    epsilon = 1.0
    
    # Using absolute paths to guarantee successful deployment
    weights_path = os.path.join(os.path.dirname(__file__), "global_orchestrator.pth")
    best_reward = -999999
    
    for ep in range(episodes):
        state_dict = reset_env()
        ep_reward = 0
        
        # Override graph logs temporarily to save terminal output spam
        import builtins
        original_print = builtins.print
        builtins.print = lambda *args, **kwargs: None
        
        for step in range(100):  
            s_obj = extract_state_object(state_dict)
            action = agent.act(s_obj, epsilon)
            
            apply_action(state_dict, action, graph)
            update_state(state_dict, graph.process_arrivals())
            
            s_next_obj = extract_state_object(state_dict)
            reward = agent.calculate_reward(s_next_obj)
            ep_reward += reward
            
            agent.remember(s_obj, action, reward, s_next_obj)
            agent.train_step()
            
        builtins.print = original_print # Restore prints
        epsilon = max(0.1, epsilon * 0.99)
        
        if ep_reward > best_reward:
            best_reward = ep_reward
            if torch:
                torch.save(agent.model.state_dict(), weights_path)
                
        if ep % 20 == 0 or ep == episodes - 1:
            print(f"Episode {ep:03d}/{episodes} | Epsilon: {epsilon:.3f} | System Reward Trend: {ep_reward/100:.2f}")

    print(f"\n✅ TRAINING COMPLETE! Dominant Weights successfully bound to: {weights_path}")

if __name__ == "__main__":
    run_matrix()
