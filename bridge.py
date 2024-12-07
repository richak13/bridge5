from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
from web3.middleware import geth_poa_middleware #Necessary for POA chains
import json
import sys
from pathlib import Path

source_chain = 'avax'
destination_chain = 'bsc'
contract_info = "contract_info.json"

def connectTo(chain):
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'bsc':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['avax','bsc']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def getContractInfo(chain):
    """
        Load the contract_info file into a dictinary
        This function is used by the autograder and will likely be useful to you
    """
    p = Path(__file__).with_name(contract_info)
    try:
        with p.open('r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( "Failed to read contract info" )
        print( "Please contact your instructor" )
        print( e )
        sys.exit(1)

    return contracts[chain]



def scanBlocks(chain):
    """
    Scan the last 5 blocks of the source and destination chains
    Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
    When Deposit events are found on the source chain, call the 'wrap' function on the destination chain
    When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """
    try:
        if chain == 'source':
            w3 = connectTo('avax')
            contracts = getContractInfo('source')
        elif chain == 'destination':
            w3 = connectTo('bsc')
            contracts = getContractInfo('destination')
        else:
            raise ValueError(f"Invalid chain: {chain}")
        
        contract = w3.eth.contract(
            address=w3.toChecksumAddress(contracts['address']),
            abi=contracts['abi']
        )
        warden_key = contracts['warden_key']

        # Get the latest block
        latest_block = w3.eth.block_number

        # Iterate through the last 5 blocks
        for block_number in range(latest_block - 5, latest_block + 1):
            block = w3.eth.get_block(block_number, full_transactions=True)

            # Iterate through transactions in the block
            for tx in block['transactions']:
                receipt = w3.eth.get_transaction_receipt(tx['hash'])

                # Decode logs
                for log in receipt['logs']:
                    try:
                        decoded_event = contract.events.Deposit().processLog(log)
                        # Call 'wrap' on the destination chain
                        destination_contract = connectTo('bsc').eth.contract(
                            address=w3.toChecksumAddress(getContractInfo('destination')['address']),
                            abi=getContractInfo('destination')['abi']
                        )
                        wrap_tx = destination_contract.functions.wrap(
                            decoded_event['args']['token'],
                            decoded_event['args']['amount']
                        ).buildTransaction({
                            'from': warden_key,
                            'nonce': w3.eth.getTransactionCount(w3.toChecksumAddress(warden_key)),
                        })
                        signed_tx = w3.eth.account.sign_transaction(wrap_tx, warden_key)
                        w3.eth.sendRawTransaction(signed_tx.rawTransaction)
                        print("Successfully processed Deposit event and called wrap on destination chain")

                    except Exception:
                        try:
                            decoded_event = contract.events.Unwrap().processLog(log)
                            # Call 'withdraw' on the source chain
                            source_contract = connectTo('avax').eth.contract(
                                address=w3.toChecksumAddress(getContractInfo('source')['address']),
                                abi=getContractInfo('source')['abi']
                            )
                            withdraw_tx = source_contract.functions.withdraw(
                                decoded_event['args']['token'],
                                decoded_event['args']['amount']
                            ).buildTransaction({
                                'from': warden_key,
                                'nonce': w3.eth.getTransactionCount(w3.toChecksumAddress(warden_key)),
                            })
                            signed_tx = w3.eth.account.sign_transaction(withdraw_tx, warden_key)
                            w3.eth.sendRawTransaction(signed_tx.rawTransaction)
                            print("Successfully processed Unwrap event and called withdraw on source chain")

                        except Exception as e:
                            print(f"Error processing logs: {e}")

    except Exception as e:
        print(f"Error in scanBlocks: {e}")
