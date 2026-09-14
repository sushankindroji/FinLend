const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const LoanRegistry = await hre.ethers.getContractFactory("LoanRegistry");
  const contract = await LoanRegistry.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("LoanRegistry deployed to:", address);

  // Write the address to a file the backend/.env setup step can read.
  const outPath = path.join(__dirname, "..", "deployed-address.json");
  fs.writeFileSync(
    outPath,
    JSON.stringify({ network: hre.network.name, address, deployedAt: new Date().toISOString() }, null, 2)
  );
  console.log(`Address written to ${outPath}`);
  console.log("\nCopy this into backend/.env as CONTRACT_ADDRESS:");
  console.log(address);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
