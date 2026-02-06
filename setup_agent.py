
import secrets
from eth_account import Account

def generate_agent():
    print("Generating Hyperliquid Agent Wallet...")
    
    # Generate a random private key
    priv = secrets.token_hex(32)
    private_key = "0x" + priv
    account = Account.from_key(private_key)
    
    print("\n" + "="*50)
    print("✅ AGENT WALLET GENERATED")
    print("="*50)
    print(f"Address:      {account.address}")
    print(f"Private Key:  {private_key}")
    print("="*50)
    
    print("\n⚠️  ACTION REQUIRED:")
    print("1. Copy the 'Address' above.")
    print("2. Go to Hyperliquid.xyz -> Trade page.")
    print("3. Connect your MAIN wallet.")
    print("4. Go to 'Manage Agent' (or API settings).")
    print("5. Paste the Agent Address and name it 'HypeBot'.")
    print("6. Approve the transaction with your main wallet.")
    print("\nThen, paste the 'Private Key' into your .env file as AGENT_PRIVATE_KEY.")

if __name__ == "__main__":
    generate_agent()
