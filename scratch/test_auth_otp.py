import httpx
import json

BASE = "http://127.0.0.1:8000/api/v1/auth"

def test_otp_endpoints():
    client = httpx.Client()
    
    # 1. Lookup farmer by mobile
    lookup = client.get(f"{BASE}/farmer-by-mobile/9814255201")
    assert lookup.status_code == 200, f"Lookup failed: {lookup.text}"
    lookup_data = lookup.json()
    print("[PASS] 1. Farmer mobile lookup:", lookup_data["name"], lookup_data["mandi_pass_id"], lookup_data["name_hi"])
    assert lookup_data["name"] == "Balwinder Singh"
    assert lookup_data["mandi_pass_id"] == "08234"

    # 2. Send OTP
    send_resp = client.post(f"{BASE}/send-otp", json={"mobile_number": "9814255201", "role": "FARMER"})
    assert send_resp.status_code == 200, f"Send OTP failed: {send_resp.text}"
    send_data = send_resp.json()
    print("[PASS] 2. Send OTP:", send_data["message"], "OTP Demo:", send_data["otp_demo"])
    assert send_data["otp_demo"] == "123456"

    # 3. Verify OTP
    verify_resp = client.post(f"{BASE}/verify-otp", json={
        "mobile_number": "9814255201",
        "otp": "123456",
        "role": "FARMER"
    })
    assert verify_resp.status_code == 200, f"Verify OTP failed: {verify_resp.text}"
    verify_data = verify_resp.json()
    print("[PASS] 3. Verify OTP issued JWT token:", verify_data["role"], verify_data["full_name"])
    assert verify_data["role"] == "FARMER"
    assert "access_token" in verify_data

    print("\nALL OTP ENDPOINTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_otp_endpoints()
