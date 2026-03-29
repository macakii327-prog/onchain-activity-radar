#!/usr/bin/env python3
"""
Continuous Deep Monitor v2
30分間隔・コントラクトTX集中度分析・ミームコイン早期発見
Solana Helius API対応
"""

import asyncio
import aiohttp
import json
import os
import signal
import subprocess
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
from complete_7chain_radar import Complete7ChainRadar

# .env読み込み
load_dotenv()

class ContinuousDeepMonitor:
    """30分間隔の深度監視システム"""
    
    def __init__(self):
        self.radar = Complete7ChainRadar()
        self.running = True
        self.interval_seconds = 30 * 60  # 30分
        self.scan_count = 0
        
        # Helius Solana API
        self.helius_key = os.getenv('HELIUS_SOLANA_API_KEY', '')
        self.helius_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}" if self.helius_key else "https://api.mainnet-beta.solana.com"
        
        # EVM RPC endpoints
        self.evm_rpcs = {
            'ethereum': 'https://eth.api.pocket.network',
            'base': 'https://base.api.pocket.network',
            'arbitrum': 'https://arb-one.api.pocket.network',
            'optimism': 'https://rpc.ankr.com/optimism',
            'polygon': 'https://rpc.ankr.com/polygon',
            'bsc': 'https://rpc.ankr.com/bsc',
        }
        
        # チェーンIDマッピング
        self.chain_to_evm = {
            'ETH': 'ethereum', 'BASE': 'base', 'ARB': 'arbitrum',
            'OP': 'optimism', 'POLYGON': 'polygon', 'BSC': 'bsc',
        }
        
        # 既知コントラクト（除外用）
        self.known_infra = {
            '0xdac17f958d2ee523a2206206994597c13d831ec7',  # USDT
            '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',  # USDC
            '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',  # WETH
            '0x0000000071727de22e5e9d8baf0edac6f37da032',  # EntryPoint v0.7
            '0x5ff137d4b0fdcd49dca30c7cf57e578a026d2789',  # EntryPoint v0.6
        }
        
        # 前回のホットコントラクト（差分検出用）
        self.prev_hot_contracts = {}
        
        # Discord webhook
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL', '')
        
        # Nansen API key
        os.environ['NANSEN_API_KEY'] = os.getenv('NANSEN_API_KEY', '')
        
        signal.signal(signal.SIGINT, self._handle_stop)
        signal.signal(signal.SIGTERM, self._handle_stop)
        
        print("🔍 Continuous Deep Monitor v2")
        print(f"⏰ Interval: {self.interval_seconds // 60} minutes")
        print(f"🌐 Solana API: {'Helius' if self.helius_key else 'Public RPC'}")
        print(f"📢 Discord: {'Configured' if self.discord_webhook and self.discord_webhook != 'your_discord_webhook_here' else 'Not set'}")
    
    def _handle_stop(self, *args):
        print("\n⏹️ Stopping monitor...")
        self.running = False
    
    # ─── EVM コントラクトTX集中度分析 ───
    
    async def analyze_evm_contract_hotspots(self, chain_id: str, num_blocks: int = 15) -> dict:
        """EVMチェーンのコントラクト別TX集中度を分析"""
        evm_name = self.chain_to_evm.get(chain_id)
        if not evm_name:
            return {}
        
        rpc_url = self.evm_rpcs[evm_name]
        contract_txs = Counter()
        contract_values = {}
        total_txs = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                # 最新ブロック取得
                resp = await session.post(rpc_url, json={
                    "jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1
                }, timeout=aiohttp.ClientTimeout(total=10))
                data = await resp.json()
                if not data or 'result' not in data:
                    return {}
                latest = int(data['result'], 16)
                
                # 複数ブロック分析
                for i in range(num_blocks):
                    block_num = latest - i
                    resp = await session.post(rpc_url, json={
                        "jsonrpc": "2.0",
                        "method": "eth_getBlockByNumber",
                        "params": [hex(block_num), True],
                        "id": 1
                    }, timeout=aiohttp.ClientTimeout(total=15))
                    block_data = await resp.json()
                    block = (block_data or {}).get('result') or {}
                    
                    for tx in block.get('transactions', []):
                        total_txs += 1
                        to_addr = tx.get('to', '')
                        if not to_addr:
                            continue
                        to_lower = to_addr.lower()
                        
                        # コントラクト呼び出し（input != 0x）のみカウント
                        inp = tx.get('input', '0x')
                        if inp and inp != '0x':
                            contract_txs[to_lower] += 1
                            val = int(tx.get('value', '0x0'), 16) / 1e18
                            contract_values[to_lower] = contract_values.get(to_lower, 0) + val
                    
                    await asyncio.sleep(0.1)  # レート制限対策
            
            # ホットコントラクト抽出（インフラ除外）
            hotspots = []
            for addr, count in contract_txs.most_common(20):
                if addr in self.known_infra:
                    continue
                if count < 3:  # 最低3TX
                    break
                
                hotspots.append({
                    'address': addr,
                    'tx_count': count,
                    'tx_per_block': round(count / num_blocks, 2),
                    'share_pct': round(count / max(total_txs, 1) * 100, 1),
                    'total_value_eth': round(contract_values.get(addr, 0), 4),
                    'is_new': addr not in self.prev_hot_contracts.get(chain_id, set()),
                })
            
            # 今回のホットコントラクトを保存
            self.prev_hot_contracts[chain_id] = {h['address'] for h in hotspots}
            
            return {
                'chain': chain_id,
                'blocks_analyzed': num_blocks,
                'total_txs': total_txs,
                'hotspots': hotspots[:8],
            }
        except Exception as e:
            print(f"  ❌ {chain_id} contract analysis error: {e}")
            return {}
    
    # ─── Solana コントラクト(Program)TX集中度分析 ───
    
    async def analyze_solana_program_hotspots(self) -> dict:
        """Solanaのプログラム別TX集中度 → ミームコイン早期発見"""
        print("🔍 Solana program hotspot analysis...")
        
        program_txs = Counter()
        total_txs = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                # 最新スロット取得
                resp = await session.post(self.helius_url, json={
                    "jsonrpc": "2.0", "method": "getSlot", "params": [], "id": 1
                }, timeout=aiohttp.ClientTimeout(total=10))
                slot = (await resp.json()).get('result', 0)
                
                if not slot:
                    return {}
                
                # 最新ブロック取得（Heliusなら詳細取得可能）
                resp = await session.post(self.helius_url, json={
                    "jsonrpc": "2.0",
                    "method": "getBlock",
                    "params": [slot, {
                        "encoding": "jsonParsed",
                        "transactionDetails": "accounts",
                        "maxSupportedTransactionVersion": 0
                    }],
                    "id": 1
                }, timeout=aiohttp.ClientTimeout(total=20))
                block = (await resp.json()).get('result', {})
                
                known_programs = {
                    '11111111111111111111111111111111': 'System',
                    'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA': 'SPL Token',
                    'ComputeBudget111111111111111111111111111111': 'ComputeBudget',
                    'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL': 'ATA',
                    'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4': 'Jupiter',
                    'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc': 'Orca Whirlpool',
                }
                
                txs = block.get('transactions', [])
                total_txs = len(txs)
                
                for tx_wrapper in txs:
                    tx = tx_wrapper.get('transaction', {})
                    account_keys = tx.get('accountKeys', [])
                    
                    # 各TXが呼び出すプログラムを集計
                    for acc in account_keys:
                        pubkey = acc.get('pubkey', '') if isinstance(acc, dict) else str(acc)
                        writable = acc.get('writable', True) if isinstance(acc, dict) else True
                        signer = acc.get('signer', False) if isinstance(acc, dict) else False
                        
                        # プログラム = writable=False, signer=False のアカウント
                        if not writable and not signer and pubkey not in known_programs:
                            program_txs[pubkey] += 1
                
                # ホットプログラム抽出
                hotspots = []
                for program, count in program_txs.most_common(15):
                    if count < 3:
                        break
                    hotspots.append({
                        'program': program,
                        'tx_count': count,
                        'share_pct': round(count / max(total_txs, 1) * 100, 1),
                        'is_new': program not in self.prev_hot_contracts.get('SOL', set()),
                    })
                
                self.prev_hot_contracts['SOL'] = {h['program'] for h in hotspots}
                
                # Helius Enhanced API でトークン情報取得（可能なら）
                if self.helius_key and hotspots:
                    await self._enrich_solana_hotspots(session, hotspots)
                
                return {
                    'chain': 'SOL',
                    'slot': slot,
                    'total_txs': total_txs,
                    'hotspots': hotspots[:8],
                }
                
        except Exception as e:
            print(f"  ❌ Solana analysis error: {e}")
            return {}
    
    async def _enrich_solana_hotspots(self, session, hotspots):
        """Helius DAS APIでプログラムの追加情報取得"""
        try:
            for hs in hotspots[:5]:
                resp = await session.post(
                    f"https://api.helius.xyz/v0/addresses/{hs['program']}/transactions?api-key={self.helius_key}&limit=1",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                if resp.status == 200:
                    txs = await resp.json()
                    if txs and isinstance(txs, list) and len(txs) > 0:
                        hs['recent_type'] = txs[0].get('type', 'UNKNOWN')
                        hs['description'] = txs[0].get('description', '')[:100]
                await asyncio.sleep(0.2)
        except Exception:
            pass
    
    # ─── コントラクト詳細取得 ───
    
    async def enrich_contract_info(self, chain_id: str, hotspots: list) -> list:
        """ホットコントラクトの詳細情報を取得"""
        if not hotspots:
            return hotspots
        
        # Blockscout エクスプローラーURL
        blockscout_urls = {
            'ETH': 'https://eth.blockscout.com',
            'BASE': 'https://base.blockscout.com',
            'ARB': 'https://arbitrum.blockscout.com',
            'OP': 'https://optimism.blockscout.com',
            'POLYGON': 'https://polygon.blockscout.com',
            'BSC': 'https://bsc.blockscout.com',
        }
        
        # Etherscan V2 chainid
        etherscan_chainids = {
            'ETH': 1, 'BASE': 8453, 'ARB': 42161,
            'OP': 10, 'POLYGON': 137, 'BSC': 56,
        }
        
        base_url = blockscout_urls.get(chain_id)
        etherscan_chainid = etherscan_chainids.get(chain_id)
        etherscan_key = os.getenv('ETHERSCAN_API_KEY', '')
        
        async with aiohttp.ClientSession() as session:
            for hs in hotspots[:6]:  # 上位6個まで
                addr = hs.get('address', hs.get('program', ''))
                if not addr:
                    continue
                
                info = {}
                
                # 1. Blockscout アドレス情報
                if base_url:
                    try:
                        resp = await session.get(
                            f"{base_url}/api/v2/addresses/{addr}",
                            timeout=aiohttp.ClientTimeout(total=8)
                        )
                        if resp.status == 200:
                            data = await resp.json()
                            info['name'] = data.get('name')
                            info['is_contract'] = data.get('is_contract', False)
                            info['is_verified'] = data.get('is_verified', False)
                            info['is_scam'] = data.get('is_scam', False)
                            
                            # トークン情報があれば取得
                            token = data.get('token')
                            if token:
                                info['token_name'] = token.get('name')
                                info['token_symbol'] = token.get('symbol')
                                info['token_type'] = token.get('type')
                                info['holders'] = token.get('holders_count')
                            
                            # creator情報
                            creator = data.get('creator_address_hash')
                            if creator:
                                info['creator'] = creator
                            
                            creation_tx = data.get('creation_transaction_hash')
                            if creation_tx:
                                info['creation_tx'] = creation_tx
                    except Exception:
                        pass
                
                # 2. Blockscout トークン情報（トークンコントラクトの場合）
                if base_url and not info.get('token_name'):
                    try:
                        resp = await session.get(
                            f"{base_url}/api/v2/tokens/{addr}",
                            timeout=aiohttp.ClientTimeout(total=5)
                        )
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('name'):
                                info['token_name'] = data.get('name')
                                info['token_symbol'] = data.get('symbol')
                                info['token_type'] = data.get('type')
                                info['holders'] = data.get('holders_count') or data.get('holders')
                                info['total_supply'] = data.get('total_supply')
                                info['exchange_rate'] = data.get('exchange_rate')
                    except Exception:
                        pass
                
                # 3. Blockscout スマートコントラクト情報
                if base_url and not info.get('name'):
                    try:
                        resp = await session.get(
                            f"{base_url}/api/v2/smart-contracts/{addr}",
                            timeout=aiohttp.ClientTimeout(total=5)
                        )
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('name'):
                                info['name'] = data.get('name')
                                info['is_verified'] = True
                    except Exception:
                        pass
                
                # 4. Etherscan V2 fallback
                if not info.get('name') and not info.get('token_name') and etherscan_chainid:
                    try:
                        resp = await session.get(
                            f"https://api.etherscan.io/v2/api?chainid={etherscan_chainid}&module=contract&action=getsourcecode&address={addr}&apikey={etherscan_key}",
                            timeout=aiohttp.ClientTimeout(total=8)
                        )
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get('result', [])
                            if isinstance(results, list) and results:
                                contract_name = results[0].get('ContractName', '')
                                if contract_name:
                                    info['name'] = contract_name
                                    info['is_verified'] = True
                    except Exception:
                        pass
                
                # 5. Explorer link生成
                explorer_links = {
                    'ETH': f'https://etherscan.io/address/{addr}',
                    'BASE': f'https://basescan.org/address/{addr}',
                    'ARB': f'https://arbiscan.io/address/{addr}',
                    'OP': f'https://optimistic.etherscan.io/address/{addr}',
                    'POLYGON': f'https://polygonscan.com/address/{addr}',
                    'BSC': f'https://bscscan.com/address/{addr}',
                    'SOL': f'https://solscan.io/account/{addr}',
                }
                info['explorer_url'] = explorer_links.get(chain_id, '')
                
                hs['info'] = info
                await asyncio.sleep(0.15)  # レート制限
        
        return hotspots
    
    async def enrich_solana_program_info(self, hotspots: list) -> list:
        """Solanaプログラムの詳細情報を取得"""
        if not hotspots or not self.helius_key:
            return hotspots
        
        async with aiohttp.ClientSession() as session:
            for hs in hotspots[:6]:
                program = hs.get('program', '')
                if not program:
                    continue
                
                info = {'explorer_url': f'https://solscan.io/account/{program}'}
                
                # Helius enhanced transaction APIでプログラムの用途推定
                try:
                    resp = await session.get(
                        f"https://api.helius.xyz/v0/addresses/{program}/transactions?api-key={self.helius_key}&limit=3",
                        timeout=aiohttp.ClientTimeout(total=8)
                    )
                    if resp.status == 200:
                        txs = await resp.json()
                        if txs and isinstance(txs, list):
                            # TX typeから用途推定
                            types = [t.get('type', '') for t in txs]
                            descriptions = [t.get('description', '')[:80] for t in txs if t.get('description')]
                            
                            info['recent_tx_types'] = list(set(types))[:3]
                            info['sample_descriptions'] = descriptions[:2]
                            
                            # token transfersがあればトークン情報
                            for tx in txs[:1]:
                                token_transfers = tx.get('tokenTransfers', [])
                                if token_transfers:
                                    mint = token_transfers[0].get('mint', '')
                                    info['related_token_mint'] = mint
                                
                                # NFT情報
                                nft_events = tx.get('events', {}).get('nft', {})
                                if nft_events:
                                    info['nft_related'] = True
                except Exception:
                    pass
                
                # Helius DAS API でアセット情報
                try:
                    resp = await session.post(
                        self.helius_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getAsset",
                            "params": {"id": program}
                        },
                        timeout=aiohttp.ClientTimeout(total=5)
                    )
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get('result', {})
                        content = result.get('content', {})
                        metadata = content.get('metadata', {})
                        if metadata.get('name'):
                            info['name'] = metadata['name']
                            info['symbol'] = metadata.get('symbol', '')
                except Exception:
                    pass
                
                hs['info'] = info
                await asyncio.sleep(0.2)
        
        return hotspots
    
    # ─── Nansen Smart Money分析 ───
    
    def run_nansen(self, cmd: list) -> dict:
        """Nansen CLIコマンド実行"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=os.environ.copy())
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception:
            pass
        return {}
    
    async def nansen_smart_money_scan(self, chain_id: str, hot_contracts: list = None) -> dict:
        """Nansen Smart Money分析 + ホットコントラクトとのクロスリファレンス"""
        chain_map = {
            'ETH': 'ethereum', 'BASE': 'base', 'ARB': 'arbitrum',
            'OP': 'optimism', 'POLYGON': 'polygon', 'BSC': 'bnb', 'SOL': 'solana'
        }
        nchain = chain_map.get(chain_id)
        if not nchain:
            return {}
        
        excluded = {
            'USDC', 'USDT', 'DAI', 'USDS', 'EURC', 'PYUSD', 'FRAX',
            'ETH', 'WETH', 'STETH', 'WSTETH', 'RETH', 'CBETH',
            'BTC', 'WBTC', 'SOL', 'WSOL', 'BNB', 'WBNB', 'MATIC', 'WMATIC',
            'UNI', 'LINK', 'AAVE', 'MKR', 'ARB', 'OP',
            'SHIB', 'DOGE', 'PEPE', 'FLOKI',
        }
        
        # ホットコントラクトのアドレスセット（小文字）
        hot_addrs = set()
        if hot_contracts:
            for hs in hot_contracts:
                addr = hs.get('address', hs.get('program', '')).lower()
                if addr:
                    hot_addrs.add(addr)
                # トークンアドレスも（info内のtoken情報から）
                info = hs.get('info', {})
                if info.get('token_symbol'):
                    hot_addrs.add(addr)
        
        results = {}
        
        # 1. Token Screener
        screener = self.run_nansen(['nansen', 'research', 'token', 'screener', '--chain', nchain, '--timeframe', '6h', '--limit', '25'])
        if screener and 'data' in screener:
            tokens = screener['data'].get('data', [])
            interesting = []
            for t in tokens:
                sym = t.get('token_symbol', '').upper()
                if sym in excluded:
                    continue
                vol = t.get('volume') or 0
                change = t.get('price_change') or 0
                age = t.get('token_age_days') or 999
                addr = (t.get('token_address') or '').lower()
                if vol >= 1000:
                    entry = {
                        'symbol': sym, 'volume': vol, 'price_change': change,
                        'age_days': age, 'market_cap': t.get('market_cap_usd', 0),
                        'token_address': addr,
                    }
                    # ホットコントラクトとマッチ？
                    if addr in hot_addrs:
                        entry['hot_contract_match'] = True
                    interesting.append(entry)
            results['trending'] = sorted(interesting, key=lambda x: x['volume'], reverse=True)[:5]
        
        # 2. Smart Money Netflow
        netflow = self.run_nansen(['nansen', 'research', 'smart-money', 'netflow', '--chain', nchain, '--limit', '20'])
        if netflow and 'data' in netflow:
            tokens = netflow['data'].get('data', [])
            flows = []
            for t in tokens:
                sym = t.get('token_symbol', '').upper()
                if sym in excluded:
                    continue
                nf = t.get('net_flow_24h_usd') or 0
                traders = t.get('trader_count') or 0
                addr = t.get('token_address', '').lower()
                if abs(nf) >= 200 or traders >= 2:
                    entry = {
                        'symbol': sym, 'net_flow': nf, 'traders': traders,
                        'age_days': t.get('token_age_days', 999),
                        'token_address': addr,
                    }
                    if addr in hot_addrs:
                        entry['hot_contract_match'] = True
                    flows.append(entry)
            results['smart_money'] = sorted(flows, key=lambda x: abs(x['net_flow']), reverse=True)[:5]
        
        # 3. SM DEX Trades（直近の実取引）
        trades = self.run_nansen(['nansen', 'research', 'smart-money', 'dex-trades', '--chain', nchain])
        if trades and 'data' in trades:
            all_trades = trades['data'].get('data', [])
            interesting_trades = []
            for tr in all_trades:
                bought_sym = tr.get('token_bought_symbol', '').upper()
                sold_sym = tr.get('token_sold_symbol', '').upper()
                bought_addr = tr.get('token_bought_address', '').lower()
                sold_addr = tr.get('token_sold_address', '').lower()
                amount = tr.get('trade_value_usd') or 0
                trader_label = tr.get('trader_address_label', '')
                timestamp = tr.get('block_timestamp', '')
                
                # ホットコントラクトに関連する取引を優先
                is_hot_match = bought_addr in hot_addrs or sold_addr in hot_addrs
                
                # 非メジャートークンの取引 or ホットマッチ
                target_sym = None
                side = None
                if bought_sym not in excluded and amount > 100:
                    target_sym = bought_sym
                    side = 'BUY'
                elif sold_sym not in excluded and amount > 100:
                    target_sym = sold_sym
                    side = 'SELL'
                
                if target_sym or is_hot_match:
                    entry = {
                        'symbol': target_sym or (bought_sym if side == 'BUY' else sold_sym),
                        'side': side or ('BUY' if bought_sym not in excluded else 'SELL'),
                        'amount_usd': amount,
                        'trader_label': trader_label or 'Smart Money',
                        'timestamp': timestamp,
                        'bought': bought_sym,
                        'sold': sold_sym,
                        'hot_contract_match': is_hot_match,
                    }
                    interesting_trades.append(entry)
            
            # ホットマッチを優先、その後金額順
            interesting_trades.sort(key=lambda x: (not x.get('hot_contract_match', False), -x['amount_usd']))
            results['sm_trades'] = interesting_trades[:6]
        
        # 4. SM Holdings（SMが大量保有してるトークン）
        holdings = self.run_nansen(['nansen', 'research', 'smart-money', 'holdings', '--chain', nchain, '--limit', '15'])
        if holdings and 'data' in holdings:
            tokens = holdings['data'].get('data', [])
            notable = []
            for t in tokens:
                sym = t.get('token_symbol', '').upper()
                if sym in excluded:
                    continue
                value = t.get('value_usd') or 0
                holders = t.get('holders_count') or 0
                change_24h = t.get('balance_24h_percent_change') or 0
                addr = t.get('token_address', '').lower()
                if value >= 1000 or holders >= 3:
                    entry = {
                        'symbol': sym,
                        'value_usd': value,
                        'sm_holders': holders,
                        'change_24h_pct': change_24h,
                        'sectors': t.get('token_sectors', []),
                        'token_address': addr,
                    }
                    if addr in hot_addrs:
                        entry['hot_contract_match'] = True
                    notable.append(entry)
            results['sm_holdings'] = sorted(notable, key=lambda x: (not x.get('hot_contract_match', False), -x['value_usd']))[:6]
        
        return results
    
    # ─── メインスキャン ───
    
    async def run_single_scan(self) -> dict:
        """1回分のスキャン実行"""
        self.scan_count += 1
        now = datetime.now()
        ts = now.strftime('%H:%M:%S')
        
        print(f"\n{'='*60}")
        print(f"🔍 DEEP SCAN #{self.scan_count} - {ts}")
        print(f"{'='*60}")
        
        # Step 1: 7チェーン波動検知
        scan_results = await self.radar.run_scan()
        
        # Step 2: 全チェーン情報 + 波動チェーン特定
        all_chains = []
        active_chains = []
        for cid, result in scan_results.items():
            if hasattr(result, 'spike_ratio'):
                info = {'chain': cid, 'spike': result.spike_ratio, 'txs': result.tx_count}
                all_chains.append(info)
                if result.spike_ratio >= 2.0 and result.tx_count > 0:
                    active_chains.append(info)
        
        all_chains.sort(key=lambda x: x['spike'], reverse=True)
        active_chains.sort(key=lambda x: x['spike'], reverse=True)
        
        if not active_chains:
            # 穏やかでも全チェーンサマリは出す
            summary = " | ".join(f"{c['chain']}:{c['spike']:.1f}x" for c in all_chains)
            print(f"🔹 市場は穏やか [{summary}]")
            return {'status': 'calm', 'all_chains': all_chains, 'timestamp': ts}
        
        print(f"🚨 {len(active_chains)} チェーンでウェーブ検出！深度分析開始")
        
        # Step 3: 各チェーンで並列深度分析
        all_results = {}
        
        for chain_info in active_chains:
            cid = chain_info['chain']
            print(f"\n📡 {cid} ({chain_info['spike']:.1f}x, {chain_info['txs']}TX) 深度分析中...")
            
            # Step A: コントラクトTX集中度分析
            if cid == 'SOL':
                contract_result = await self.analyze_solana_program_hotspots()
            else:
                contract_result = await self.analyze_evm_contract_hotspots(cid, num_blocks=15)
            
            chain_result = {'wave': chain_info}
            chain_result['contract_hotspots'] = contract_result if isinstance(contract_result, dict) else {}
            
            # Step B: コントラクト詳細情報をenrich
            hotspots = chain_result.get('contract_hotspots', {}).get('hotspots', [])
            if hotspots:
                print(f"  🔎 コントラクト詳細取得中...")
                if cid == 'SOL':
                    await self.enrich_solana_program_info(hotspots)
                else:
                    await self.enrich_contract_info(cid, hotspots)
            
            # Step C: Nansen SM分析（ホットコントラクト情報を渡してクロスリファレンス）
            print(f"  🧠 スマートマネー分析中...")
            try:
                sm_result = await self.nansen_smart_money_scan(cid, hot_contracts=hotspots)
                chain_result['smart_money'] = sm_result
            except Exception as e:
                chain_result['smart_money'] = {'error': str(e)}
            
            all_results[cid] = chain_result
        
        # Step 4: レポート生成
        report = self._build_report(all_results, ts)
        
        # Step 5: ファイル保存
        filename = f"deep_scan_{now.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"💾 {filename}")
        
        # Step 6: Discord通知
        await self._send_discord(report)
        
        return {'status': 'active', 'chains': len(all_results), 'all_chains': all_chains, 'report': report, 'timestamp': ts}
    
    def _build_report(self, results: dict, ts: str) -> str:
        """レポート文字列生成"""
        lines = [f"🔍 **DEEP SCAN RESULTS** - {ts}", ""]
        
        for cid, data in results.items():
            wave = data['wave']
            spike = wave['spike']
            wave_icon = "🌋" if spike >= 10 else "🌊" if spike >= 5 else "🔶" if spike >= 3 else "🔸" if spike >= 1.5 else "🔹"
            lines.append(f"{wave_icon} **{cid}**: {spike:.1f}x spike ({wave['txs']} TX)")
            
            # コントラクトホットスポット
            hotspots = data.get('contract_hotspots', {}).get('hotspots', [])
            if hotspots:
                lines.append("  ⚡ **ホットコントラクト:**")
                for hs in hotspots[:5]:
                    addr = hs.get('address', hs.get('program', ''))
                    new_tag = " 🆕" if hs.get('is_new') else ""
                    info = hs.get('info', {})
                    
                    # ラベル構築
                    label = ""
                    if info.get('token_name'):
                        sym = info.get('token_symbol', '')
                        holders = info.get('holders')
                        label = f"🪙 **{info['token_name']}**" + (f" ({sym})" if sym else "")
                        if holders:
                            try:
                                label += f" | {int(holders):,} holders"
                            except (ValueError, TypeError):
                                label += f" | {holders} holders"
                    elif info.get('name'):
                        label = f"📋 **{info['name']}**"
                    else:
                        label = "❓ 不明コントラクト"
                    
                    # 検証/スキャムフラグ
                    if info.get('is_scam'):
                        label += " 🚨SCAM"
                    elif info.get('is_verified'):
                        label += " ✅"
                    
                    # Solana用
                    if info.get('recent_tx_types'):
                        label += f" | {', '.join(info['recent_tx_types'][:2])}"
                    if info.get('sample_descriptions'):
                        label += f" | {info['sample_descriptions'][0][:50]}"
                    if info.get('nft_related'):
                        label += " 🖼️NFT"
                    
                    # Explorer link
                    explorer = info.get('explorer_url', '')
                    
                    lines.append(f"    🔥 {label} — {hs['tx_count']}TX ({hs['share_pct']}%){new_tag}")
                    lines.append(f"      `{addr}`")
                    if explorer:
                        lines.append(f"      <{explorer}>")
            
            # Smart Money
            sm = data.get('smart_money', {})
            trending = sm.get('trending', [])
            if trending:
                lines.append("  📈 **トレンドトークン (非メジャー):**")
                for t in trending[:3]:
                    icon = "🟢" if t['price_change'] > 0 else "🔴"
                    age_tag = f" ({t['age_days']}d)" if t['age_days'] <= 30 else ""
                    lines.append(f"    {icon} **{t['symbol']}**: ${t['volume']:,.0f} vol | {t['price_change']:+.1%}{age_tag}")
            
            sm_flows = sm.get('smart_money', [])
            if sm_flows:
                lines.append("  🧠 **SM Netflow:**")
                for f in sm_flows[:3]:
                    icon = "📈" if f['net_flow'] > 0 else "📉"
                    age_tag = f" 🆕{f['age_days']}d" if f['age_days'] <= 14 else ""
                    hot_tag = " 🔗HOT" if f.get('hot_contract_match') else ""
                    lines.append(f"    {icon} **{f['symbol']}**: ${abs(f['net_flow']):,.0f} ({f['traders']}人){age_tag}{hot_tag}")
            
            # SM直近トレード
            sm_trades = sm.get('sm_trades', [])
            if sm_trades:
                lines.append("  💰 **SM直近トレード:**")
                for tr in sm_trades[:4]:
                    side_icon = "🟢BUY" if tr['side'] == 'BUY' else "🔴SELL"
                    hot_tag = " 🔗" if tr.get('hot_contract_match') else ""
                    trader = tr.get('trader_label', 'SM')
                    lines.append(f"    {side_icon} **{tr['symbol']}** ${tr['amount_usd']:,.0f} by {trader}{hot_tag}")
                    if tr.get('hot_contract_match'):
                        lines.append(f"      ↳ ⚡ ホットコントラクトに関連！")
            
            # SM Holdings
            sm_hold = sm.get('sm_holdings', [])
            if sm_hold:
                lines.append("  🏦 **SM保有ポジション:**")
                for h in sm_hold[:4]:
                    change = h.get('change_24h_pct', 0)
                    change_icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                    change_str = f" ({change:+.1f}% 24h)" if change else ""
                    hot_tag = " 🔗HOT" if h.get('hot_contract_match') else ""
                    sectors = ", ".join(h.get('sectors', [])[:2])
                    sector_str = f" [{sectors}]" if sectors else ""
                    lines.append(f"    {change_icon} **{h['symbol']}**: ${h['value_usd']:,.0f} ({h['sm_holders']}人保有){change_str}{hot_tag}{sector_str}")
            
            lines.append("")
        
        lines.append("🔍 30分間隔 深度分析モード")
        return "\n".join(lines)
    
    async def _send_discord(self, message: str):
        """Discord通知（ファイルに書き出し→外部から読み取り）"""
        # レポートをファイルに書き出し（OpenClawが読んでDiscordに投稿）
        try:
            with open('latest_report.txt', 'w') as f:
                f.write(message)
            print(f"📢 レポート保存: latest_report.txt")
        except Exception:
            pass
    
    # ─── 継続ループ ───
    
    async def run_continuous(self):
        """30分間隔の継続監視ループ"""
        print(f"\n🚀 30分間隔 深度監視開始！")
        print(f"   Ctrl+C で停止\n")
        
        while self.running:
            try:
                result = await self.run_single_scan()
                status = result.get('status', 'unknown')
                
                if status == 'calm':
                    print(f"💤 次のスキャン: 30分後")
                else:
                    print(f"✅ スキャン完了 - 次: 30分後")
                
            except Exception as e:
                print(f"❌ スキャンエラー: {e}")
            
            # 30分待機（1分ごとにチェック）
            for _ in range(self.interval_seconds // 60):
                if not self.running:
                    break
                await asyncio.sleep(60)
        
        print("⏹️ 監視終了")


async def main():
    import sys
    monitor = ContinuousDeepMonitor()
    
    if '--once' in sys.argv:
        # 単発実行
        await monitor.run_single_scan()
    else:
        # 継続監視
        await monitor.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
