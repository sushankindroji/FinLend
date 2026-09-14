const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("LoanRegistry", function () {
  let contract;
  let owner, lender, borrower;

  beforeEach(async function () {
    [owner, lender, borrower] = await ethers.getSigners();
    const LoanRegistry = await ethers.getContractFactory("LoanRegistry");
    contract = await LoanRegistry.deploy();
    await contract.waitForDeployment();
  });

  it("sets the deployer as owner", async function () {
    expect(await contract.owner()).to.equal(owner.address);
  });

  it("records a funding event and emits LoanFunded", async function () {
    await expect(contract.connect(lender).recordFunding("loan-1", "lender-ref-1", 1000))
      .to.emit(contract, "LoanFunded")
      .withArgs("loan-1", "lender-ref-1", 1000, anyValue());

    expect(await contract.fundingEventCount()).to.equal(1);
    expect(await contract.totalFundedForLoan("loan-1")).to.equal(1000);
  });

  it("accumulates multiple partial fundings for the same loan", async function () {
    await contract.recordFunding("loan-2", "lender-A", 400);
    await contract.recordFunding("loan-2", "lender-B", 600);
    expect(await contract.totalFundedForLoan("loan-2")).to.equal(1000);
    expect(await contract.fundingEventCount()).to.equal(2);
  });

  it("records a repayment event and emits LoanRepaid", async function () {
    await expect(contract.connect(borrower).recordRepayment("loan-1", "borrower-ref-1", 1100))
      .to.emit(contract, "LoanRepaid")
      .withArgs("loan-1", "borrower-ref-1", 1100, anyValue());

    expect(await contract.repaymentEventCount()).to.equal(1);
    expect(await contract.totalRepaidForLoan("loan-1")).to.equal(1100);
  });

  it("rejects zero-amount funding", async function () {
    await expect(contract.recordFunding("loan-1", "lender-1", 0)).to.be.revertedWith(
      "LoanRegistry: amount must be > 0"
    );
  });

  it("rejects zero-amount repayment", async function () {
    await expect(contract.recordRepayment("loan-1", "borrower-1", 0)).to.be.revertedWith(
      "LoanRegistry: amount must be > 0"
    );
  });
});

// Small helper since chai-matchers' anyValue is in a separate import path
// across toolbox versions; this local implementation avoids version drift.
function anyValue() {
  return (x) => true;
}
