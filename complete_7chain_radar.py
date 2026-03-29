#!/usr/bin/env python3
"""
Complete 7-Chain OnChain Activity Radar
全チェーン同時監視システム（完全無料RPC）
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class ChainActivity:
    """チェーン活動データ"""
    chain: str
    name: str
    latest_block: int
    tx_count: int
    gas_used: int
    spike_ratio: float
    wave_type: str
    status: str
    timestamp: datetime

class Complete7ChainRadar:
    """7チェーン完全監視システム"""
    
    def __init__(self):
        self.chains = {
            'ETH': {
                'name': 'Ethereum',
                'rpc': 'https://eth.api.pocket.network',
                'baseline_tx': 100
            },
            'POLYGON': {
                'name': 'Polygon',
                'rpc': 'https://rpc.ankr.com/polygon',
                'baseline_tx': 80
            },
            'ARB': {
                'name': 'Arbitrum One',
                'rpc': 'https://arb-one.api.pocket.network',
                'baseline_tx': 60
            },
            'BASE': {
                'name': 'Base',
                'rpc': 'https://base.api.pocket.network',
                'baseline_tx': 40
            },
            'OP': {
                'name': 'Optimism',
                'rpc': 'https://optimism.publicnode.com',
                'baseline_tx': 50
            },
            'BSC': {
                'name': 'BNB Smart Chain',
                'rpc': 'https://bsc-dataseed.binance.org',
                'baseline_tx': 120
            },
            'SOL': {
                'name': 'Solana',
                'rpc': 'https://api.mainnet-beta.solana.com',
                'baseline_tx': 3000
            }
        }
        
        print("🚀 Complete 7-Chain Radar initialized")
        print(f"📡 Monitoring {len(self.chains)} chains (100% FREE!)")
    
    async def scan_evm_chain(self, chain_id: str) -> Optional[ChainActivity]:
        """EVMチェーン監視"""
        config = self.chains[chain_id]
        
        try:
            async with aiohttp.ClientSession() as session:
                # 最新ブロック取得
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                }
                
                async with session.post(config['rpc'], json=payload, timeout=10) as response:
                    if response.status != 200:
                        return None
                        
                    data = await response.json()
                    latest_block_hex = data.get('result', '0x0')
                    latest_block = int(latest_block_hex, 16)
                    
                    # ブロック詳細取得
                    block_payload = {
                        "jsonrpc": "2.0",
                        "method": "eth_getBlockByNumber", 
                        "params": ["latest", False],
                        "id": 2
                    }
                    
                    async with session.post(config['rpc'], json=block_payload, timeout=10) as block_response:
                        if block_response.status != 200:
                            return None
                            
                        block_data = await block_response.json()
                        block_info = block_data.get('result', {})
                        
                        tx_hashes = block_info.get('transactions', [])
                        tx_count = len(tx_hashes)
                        
                        gas_used_hex = block_info.get('gasUsed', '0x0')
                        gas_used = int(gas_used_hex, 16) if gas_used_hex != '0x0' else 0
                        
                        # Wave判定
                        baseline = config['baseline_tx']
                        spike_ratio = tx_count / baseline if baseline > 0 else 1.0
                        
                        if spike_ratio > 3.0:
                            wave_type = "🌊 SURGE"
                        elif spike_ratio > 2.0:
                            wave_type = "🔶 STRONG"
                        elif spike_ratio > 1.5:
                            wave_type = "🔸 MODERATE"
                        else:
                            wave_type = "🔹 CALM"
                        
                        return ChainActivity(
                            chain=chain_id,
                            name=config['name'],
                            latest_block=latest_block,
                            tx_count=tx_count,
                            gas_used=gas_used,
                            spike_ratio=spike_ratio,
                            wave_type=wave_type,
                            status='success',
                            timestamp=datetime.now()
                        )
                        
        except Exception as e:
            print(f"❌ {chain_id}: {e}")
            return None
    
    async def scan_solana(self) -> Optional[ChainActivity]:
        """Solana監視"""
        config = self.chains['SOL']
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSlot",
                    "params": []
                }
                
                async with session.post(config['rpc'], json=payload, timeout=10) as response:
                    if response.status != 200:
                        return None
                        
                    data = await response.json()
                    latest_slot = data.get('result', 0)
                    
                    # ブロック詳細
                    block_payload = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "getBlock",
                        "params": [latest_slot, {"encoding": "json", "transactionDetails": "signatures"}]
                    }
                    
                    async with session.post(config['rpc'], json=block_payload, timeout=10) as block_response:
                        if block_response.status != 200:
                            return None
                            
                        block_data = await block_response.json()
                        block_info = block_data.get('result', {})
                        
                        if not block_info:
                            tx_count = 0
                        else:
                            transactions = block_info.get('transactions', [])
                            tx_count = len(transactions)
                        
                        # Solana Wave判定
                        baseline = config['baseline_tx']
                        spike_ratio = tx_count / baseline if baseline > 0 else 1.0
                        
                        if spike_ratio > 2.0:
                            wave_type = "🌊 SURGE"
                        elif spike_ratio > 1.5:
                            wave_type = "🔶 STRONG"
                        elif spike_ratio > 1.2:
                            wave_type = "🔸 MODERATE"
                        else:
                            wave_type = "🔹 CALM"
                        
                        return ChainActivity(
                            chain='SOL',
                            name=config['name'],
                            latest_block=latest_slot,
                            tx_count=tx_count,
                            gas_used=0,
                            spike_ratio=spike_ratio,
                            wave_type=wave_type,
                            status='success',
                            timestamp=datetime.now()
                        )
                        
        except Exception as e:
            print(f"❌ SOL: {e}")
            return None
    
    async def run_scan(self) -> Dict[str, ChainActivity]:
        """全チェーンスキャン実行"""
        print("🌊 COMPLETE 7-CHAIN WAVE SCAN")
        print("=" * 35)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🆓 100% FREE - No API Keys Required")
        
        tasks = []
        
        # EVMチェーン
        for chain_id in ['ETH', 'POLYGON', 'ARB', 'BASE', 'OP', 'BSC']:
            tasks.append((chain_id, self.scan_evm_chain(chain_id)))
        
        # Solana
        tasks.append(('SOL', self.scan_solana()))
        
        # 結果収集
        results = {}
        for chain_id, task in tasks:
            result = await task
            if result:
                results[chain_id] = result
                print(f"✅ {result.name}: {result.wave_type} (Block: {result.latest_block:,}, TX: {result.tx_count})")
            else:
                print(f"❌ {self.chains[chain_id]['name']}: Failed")
        
        return results
    
    async def generate_report(self, results: Dict[str, ChainActivity]) -> Dict:
        """レポート生成"""
        print(f"\n🎯 COMPLETE WAVE REPORT")
        print("=" * 25)
        
        active_chains = len(results)
        total_txs = sum(r.tx_count for r in results.values())
        avg_spike = sum(r.spike_ratio for r in results.values()) / active_chains if active_chains > 0 else 0
        
        # Wave分類
        surge = [r for r in results.values() if "SURGE" in r.wave_type]
        strong = [r for r in results.values() if "STRONG" in r.wave_type]
        moderate = [r for r in results.values() if "MODERATE" in r.wave_type]
        
        if surge:
            status = "🌊 MARKET SURGE"
            alert = "CRITICAL"
        elif strong:
            status = "🔶 STRONG WAVES"
            alert = "HIGH"
        elif moderate:
            status = "🔸 MODERATE ACTIVITY"
            alert = "MEDIUM"
        else:
            status = "🔹 CALM WATERS"
            alert = "LOW"
        
        print(f"📊 Active Chains: {active_chains}/7")
        print(f"⚡ Total TX: {total_txs:,}")
        print(f"📈 Avg Spike: {avg_spike:.2f}x")
        print(f"🌊 Status: {status}")
        print(f"🚨 Alert: {alert}")
        
        if alert in ['CRITICAL', 'HIGH']:
            high_activity = [r.name for r in surge + strong]
            print(f"\n🔔 HIGH ACTIVITY: {', '.join(high_activity)}")
            print("💡 Monitor for opportunities!")
        
        return {
            'status': status,
            'alert_level': alert,
            'active_chains': active_chains,
            'total_transactions': total_txs,
            'average_spike': avg_spike,
            'chains': {chain: result.__dict__ for chain, result in results.items()},
            'timestamp': datetime.now().isoformat()
        }

async def main():
    """メイン実行"""
    print("🔥 COMPLETE 7-CHAIN ONCHAIN RADAR")
    print("=" * 40)
    
    start_time = time.time()
    radar = Complete7ChainRadar()
    
    # スキャン実行
    results = await radar.run_scan()
    report = await radar.generate_report(results)
    
    # 保存
    duration = time.time() - start_time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"complete_7chain_scan_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n💾 Report: {filename}")
    print(f"⚡ Duration: {duration:.2f}s")
    print(f"💰 Cost: $0.00 (FREE)")
    
    return report

if __name__ == "__main__":
    result = asyncio.run(main())