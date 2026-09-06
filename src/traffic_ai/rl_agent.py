import os
import collections

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    import torch.nn.functional as F
except ImportError:
    torch = None

class GlobalTrafficState:
    """PHASE 3: Multi-Node Orchestration State."""
    def __init__(self, densities: list, flows: list):
        self.densities = densities  # [silk_board, madiwala, koramangala]
        self.flows = flows          # [silk_board, madiwala, koramangala]
        
    def to_tensor(self):
        if torch:
            return torch.FloatTensor(self.densities + self.flows)
        return self.densities + self.flows

if torch:
    class TrafficQNetwork(nn.Module):
        """DeepMind-style Global Optimizer Network."""
        def __init__(self):
            super(TrafficQNetwork, self).__init__()
            # 6 Inputs mapping to Global Graph
            self.fc1 = nn.Linear(6, 64)
            self.fc2 = nn.Linear(64, 32)
            # 4 Structured Actions (Decrease, Maintain, Increase, Force_Flush)
            self.out = nn.Linear(32, 4) 

        def forward(self, x):
            x = F.relu(self.fc1(x))
            x = F.relu(self.fc2(x))
            return self.out(x)

class DeepRLRewardEngine:
    """Phase 3 Global Orchestrator natively combating Gridlock Spillovers."""
    def __init__(self):
        self.memory = collections.deque(maxlen=10000)
        self.reward_buffer = collections.deque(maxlen=10) # Temporal Credit Assignment Buffer
        self.gamma = 0.95
        self.batch_size = 32
        
        if torch:
            self.model = TrafficQNetwork()
            self.optimizer = optim.Adam(self.model.parameters(), lr=1e-4) # Resilient Learning Rate
            self.criterion = nn.MSELoss()
            
            self.weights_path = "global_orchestrator.pth"
            if os.path.exists(self.weights_path):
                try:
                    self.model.load_state_dict(torch.load(self.weights_path))
                except Exception:
                    print("Initialized Fresh Global Matrix.")

    def act(self, global_state: GlobalTrafficState, epsilon: float = 0.0) -> int:
        if torch:
            import random
            # Epsilon-Greedy Exploration Protocol
            if random.random() < epsilon:
                return random.randint(0, 3) 
            with torch.no_grad():
                tensor_state = global_state.to_tensor()
                q_values = self.model(tensor_state)
                return torch.argmax(q_values).item()
        return 0

    def calculate_reward(self, global_state: GlobalTrafficState) -> float:
        """
        Instead of mapping local intersection bounds, this enforces:
        "Don't send traffic where it will die."
        """
        # 1. Macro Delay Tracker
        total_system_delay = sum(global_state.densities) * 50.0
        
        # 2. Node Saturation (Congestion Penalty)
        congestion_penalty = 0
        for density in global_state.densities:
            if density > 0.8:
                congestion_penalty += 100
                
        # 3. Directed Flow Collisions (Spillback Penalty)
        # If Silk Board pushes > 15 flows towards Madiwala when Madiwala is > 0.7 saturated:
        spillback_penalty = 0
        if len(global_state.flows) > 1 and global_state.flows[0] > 150.0 and global_state.densities[1] > 0.7:
            spillback_penalty += 300 # Massive violation! The AI pushed traffic into a wall!
            
        current_reward = -(total_system_delay + congestion_penalty + spillback_penalty)
        
        # CORE FIX: Temporal Delay Assignment Architecture
        self.reward_buffer.append(current_reward)
        if len(self.reward_buffer) == self.reward_buffer.maxlen:
            # Averages reward spanning physical travel time
            delayed_reward = sum(self.reward_buffer) / len(self.reward_buffer)
        else:
            delayed_reward = current_reward
            
        return float(round(delayed_reward, 2))

    def remember(self, state, action, reward, next_state):
        if torch:
            self.memory.append((state.to_tensor(), action, reward, next_state.to_tensor()))

    def train_step(self):
        if not torch or len(self.memory) < self.batch_size:
            return
            
        import random
        batch = random.sample(self.memory, self.batch_size)
        
        for state, action, reward, next_state in batch:
            # Bellman Equation execution for Global Flow
            target = reward + self.gamma * torch.max(self.model(next_state)).item()
            pred = self.model(state)[action]
            
            loss = self.criterion(pred, torch.tensor(target))
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
