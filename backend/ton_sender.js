#!/usr/bin/env node
// Node-based TON sender using @ton/ton (supports wallet v5r1). Built to avoid Python-side BOC assembly.
import { TonClient, WalletContractV5R1, WalletContractV4, internal, beginCell, SendMode, Address } from "@ton/ton";
import { mnemonicToPrivateKey } from "@ton/crypto";

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {};
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i];
    const val = args[i + 1];
    if (!val || val.startsWith("--")) continue;
    if (key === "--to") out.to = val;
    if (key === "--amount") out.amount = val;
    if (key === "--comment") out.comment = val;
  }
  if (!out.to) throw new Error("Missing --to");
  if (!out.amount) throw new Error("Missing --amount");
  return out;
}

async function main() {
  const { to, amount, comment } = parseArgs();

  const seed = process.env.TON_WALLET_SEED;
  if (!seed) throw new Error("TON_WALLET_SEED is not set");

  const apiUrl = process.env.TONCENTER_API_URL || "https://toncenter.com/api/v2/jsonRPC";
  const apiKey = process.env.TONCENTER_API_KEY || undefined;

  const mnemonic = seed.trim().split(/\s+/);
  if (mnemonic.length !== 24) {
    throw new Error(`Invalid mnemonic length: expected 24 words, got ${mnemonic.length}`);
  }

  const { publicKey, secretKey } = await mnemonicToPrivateKey(mnemonic);

  const client = new TonClient({
    endpoint: apiUrl,
    apiKey,
    timeout: 20000
  });

  // Prefer wallet v5r1 (Tonkeeper W5). Fallback to v4 if v5 is not supported.
  let wallet;
  try {
    wallet = WalletContractV5R1.create({ workchain: 0, publicKey });
  } catch (_) {
    wallet = WalletContractV4.create({ workchain: 0, publicKey });
  }

  const envAddress = process.env.TON_WALLET_ADDRESS;
  if (envAddress) {
    const calcAddr = wallet.address.toString({ urlSafe: true, bounceable: true });
    if (calcAddr !== envAddress) {
      console.error(`⚠️ Warning: Derived address ${calcAddr} differs from TON_WALLET_ADDRESS ${envAddress}`);
    }
  }

  const seqno = await client.getWalletSeqno(wallet.address);

  const body = comment
    ? beginCell().storeUint(0, 32).storeStringTail(comment).endCell()
    : undefined;

  const transfer = wallet.createTransfer({
    seqno,
    secretKey,
    sendMode: SendMode.PAY_GAS_SEPARATELY,
    messages: [
      internal({
        to: Address.parse(to),
        value: BigInt(amount),
        bounce: true,
        body
      })
    ]
  });

  await client.sendExternalMessage(wallet, transfer);
  const txHash = transfer.hash().toString("hex");

  console.log(JSON.stringify({ ok: true, txHash, seqno }));
}

main().catch((err) => {
  console.error(JSON.stringify({ ok: false, error: err.message || String(err) }));
  process.exit(1);
});

