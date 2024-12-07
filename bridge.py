from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from pathlib import Path


contract_info_file = "contract_info.json"

def connectTo(chain):
    if chain == 'avax':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # Avalanche Testnet
    if chain == 'bsc':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BNB Testnet
    else:
        raise ValueError("Unsupported chain")

    try:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return w3
    except Exception as e:
        print(f"Failed to connect to {chain} RPC: {e}")
        return None

def getContractInfo(chain):
    try:
        with open(contract_info_file, 'r') as f:
            contracts = json.load(f)
        return contracts[chain]
    except Exception as e:
        print(f"Error loading contract info: {e}")
        return None

def scanBlocks(chain):
    """
    Scan the last 5 blocks of the source and destination chains.
    Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain.
    When Deposit events are found on the source chain, call the 'wrap' function on the destination chain.
    When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain.
    """
    contracts = getContractInfo(chain)
    if not contracts:
        print(f"Failed to load contracts for {chain}")
        return

    if chain == 'source':
        other_chain = 'destination'
    elif chain == 'destination':
        other_chain = 'source'
    else:
        print(f"Invalid chain: {chain}")
        return

    # Connect to both chains
    w3 = connectTo(chain)
    other_w3 = connectTo(other_chain)
    if not w3 or not other_w3:
        return

    # Load contract details
    contract_address = contracts['address']
    contract_abi = contracts['abi']
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    # Get the latest blocks to scan
    end_block = w3.eth.get_block_number()
    start_block = end_block - 5  # Scan the last 5 blocks

    if chain == 'source':
        # Listen for Deposit events
        event_filter = contract.events.Deposit.create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()

        if not events:
            print("No Deposit events found.")
            return

        for evt in events:
            print(f"Detected Deposit event: {evt}")
            token = evt.args['token']
            recipient = evt.args['recipient']
            amount = evt.args['amount']

            # Call wrap() on the destination contract
            dest_contracts = getContractInfo('destination')
            dest_contract = other_w3.eth.contract(address=dest_contracts['address'], abi=dest_contracts['abi'])
            private_key = "0xdbd9d083e26ca8abdeb4f79e524f9ea862c2a718d2de48169b05ab3aac7a97c2"
            sender_address = "0x380A72Da9b73bf597d7f840D21635CEE26aa3dCf"
            nonce = other_w3.eth.get_transaction_count(Web3.to_checksum_address(sender_address))

            tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                'chainId': 97,  # BSC Testnet chain ID
                'gas': 2000000,
                'gasPrice': other_w3.eth.gas_price,
                'nonce': nonce,
            })

            signed_tx = other_w3.eth.account.sign_transaction(tx, private_key=private_key)
            tx_hash = other_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"wrap() called on destination chain with tx hash: {tx_hash.hex()}")

    elif chain == 'destination':
        # Listen for Unwrap events
        event_filter = contract.events.Unwrap.create_filter(fromBlock=start_block, toBlock=end_block)
        events = event_filter.get_all_entries()

        if not events:
            print("No Unwrap events found.")
            return

        for evt in events:
            print(f"Detected Unwrap event: {evt}")
            token = evt.args['underlying_token']
            recipient = evt.args['to']
            amount = evt.args['amount']

            # Call withdraw() on the source contract
            source_contracts = getContractInfo('source')
            source_contract = other_w3.eth.contract(address=source_contracts['address'], abi=source_contracts['abi'])
            private_key = "69593227abfe0f42dea95240ad20f1173618585b38a326352e1076cd0642f157"
            sender_address = "0x433356818AeB914431E309F1D2890494B103fd63"
            nonce = other_w3.eth.get_transaction_count(Web3.to_checksum_address(sender_address))

            tx = source_contract.functions.withdraw(token, recipient, amount).build_transaction({
                'chainId': 43113,  # Avalanche Fuji Testnet chain ID
                'gas': 2000000,
                'gasPrice': other_w3.eth.gas_price,
                'nonce': nonce,
            })

            signed_tx = other_w3.eth.account.sign_transaction(tx, private_key=private_key)
            tx_hash = other_w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"withdraw() called on source chain with tx hash: {tx_hash.hex()}")
