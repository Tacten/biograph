import { describe, expect, it } from "vitest";
import { aadhaarError, addressError, mobileError } from "./validate";

describe("validators", () => {
  it("accepts a 12-digit Aadhaar with spaces, refuses anything else before any call", () => {
    expect(aadhaarError("1234 5678 9012")).toBeNull();
    expect(aadhaarError("")).toMatch(/12-digit/);
    expect(aadhaarError("12345678901")).toMatch(/exactly 12 digits \(you entered 11\)/);
    expect(aadhaarError("1234567890123")).toMatch(/13/);
    expect(aadhaarError("12345678901a")).toMatch(/digits only/);
  });

  it("accepts a 10-digit Indian mobile only", () => {
    expect(mobileError("98765 43210")).toBeNull();
    expect(mobileError("987654321")).toMatch(/exactly 10 digits \(you entered 9\)/);
    expect(mobileError("5876543210")).toMatch(/starts with 6, 7, 8 or 9/);
    expect(mobileError("98765x3210")).toMatch(/digits only/);
  });

  it("applies ABDM's ABHA address policy", () => {
    expect(addressError("asha.verma")).toBeNull();
    expect(addressError("Asha1988")).toBeNull();
    expect(addressError("1asha")).toMatch(/begin with a digit/);
    expect(addressError(".asha")).toMatch(/dot/);
    expect(addressError("asha.")).toMatch(/dot/);
    expect(addressError("9876543210")).toMatch(/mobile number/);
    expect(addressError("asha_verma")).toMatch(/letters, digits and dots/i);
    expect(addressError("")).toMatch(/Enter/);
  });
});
