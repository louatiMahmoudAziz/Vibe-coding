# Deploying on AWS (single EC2 instance)

The workshop runs on one small EC2 box. SQLite lives on local disk, the
gateway's rate limiter is in-process, and the evaluator takes 0.1 s per
submission — so one instance is genuinely enough for 20-40 participants.
Do not reach for ECS or Lambda; both break assumptions this server makes.

---

## 1. Launch the instance

| setting | value | why |
| --- | --- | --- |
| AMI | Amazon Linux 2023 | Python 3.9+ and the AWS CLI are preinstalled |
| Type | `t3.small` | evaluation is 0.1 s; the model call is network-bound |
| Subnet | **public**, auto-assign public IP | see step 2 — this is the classic trap |
| Storage | 20 GB gp3 | plenty |
| Key pair | your own | for SSH |

Attach an **Elastic IP** so the URL on your slide survives a reboot.

## 2. Networking — the failure that ruins workshops

The instance must be able to reach `generativelanguage.googleapis.com`
outbound. A private subnet with no NAT gateway gives you a server that
looks perfectly healthy and fails every single generation.

**Security group**

| direction | port | source | purpose |
| --- | --- | --- | --- |
| inbound | 22 | your IP only | SSH |
| inbound | 8000 | the venue's network (or `0.0.0.0/0`) | participants |
| outbound | 443 | `0.0.0.0/0` | Gemini API |

`scripts/preflight.py` tests this explicitly. Run it the moment the box exists.

## 3. IAM role for the API key

Create a role for EC2 with this inline policy, and attach it to the instance:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "secretsmanager:GetSecretValue",
    "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:vibe-challenge/gemini-*"
  }]
}
```

Read access to exactly one secret. Nothing else.

## 4. Store the key

From your laptop (not the instance):

```bash
aws secretsmanager create-secret \
  --name vibe-challenge/gemini \
  --secret-string 'AIza...'
```

The key never touches the instance's disk, the repo, or shell history.
To rotate: delete the key in AI Studio, create a new one,
`aws secretsmanager update-secret`, then restart the service. No redeploy.

SSM Parameter Store works identically and is free — use `VCC_SSM_PARAM`
instead of `VCC_SECRET_ID`, with `ssm:GetParameter` in the policy.

## 5. Install

```bash
ssh ec2-user@<elastic-ip>

sudo dnf install -y git python3-pip
sudo mkdir -p /opt/vibe-challenge && sudo chown ec2-user:ec2-user /opt/vibe-challenge
git clone https://github.com/naderagentx/Vibe-Coding-Challenge.git /opt/vibe-challenge
cd /opt/vibe-challenge
pip3 install --user boto3        # only needed for the AWS secret path
```

## 6. Configure

```bash
export VCC_MODEL=gemini-2.5-flash
export VCC_SECRET_ID=vibe-challenge/gemini
export AWS_REGION=eu-west-1          # your region
export VCC_BUDGET_TOKENS=35000       # ~16 generations per participant
export VCC_MAX_CONCURRENT=8
export VCC_TARGET_RPM=800            # ~80% of your AI Studio limit
```

`VCC_TARGET_RPM` is the one number to get right. Read your real limit at
<https://aistudio.google.com/rate-limit> (toggle **All models**, find
`gemini-2.5-flash`) and set this to about 80 % of it. Measured behaviour
with 20 simultaneous submits:

| concurrency | target RPM | worst wait |
| --- | --- | --- |
| 4 | 60 | 78 s |
| 4 | 300 | 17 s |
| 8 | 600 | 10 s |
| 10 | 2400 | 5 s |

Too low serialises everyone behind the spacer. Too high just means the
429 backoff does the shaping instead — which works, but wastes a retry.

## 7. Preflight

```bash
python3 scripts/preflight.py
```

Ten checks, including a real end-to-end generation costing a fraction of a
cent. It exits non-zero if anything would break the workshop. **Do not skip
this**, and do not run it for the first time on the morning of the event.

## 8. Run it as a service

Copy `scripts/vibe-challenge.service` to `/etc/systemd/system/`, edit the
`Environment=` lines to match step 6, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vibe-challenge
sudo systemctl status vibe-challenge
journalctl -u vibe-challenge -f      # live logs
```

`Restart=always` means a crash mid-workshop recovers in three seconds
instead of ending the session.

## 9. Calibrate the model

```bash
python3 scripts/calibrate_model.py --model gemini-2.5-flash
```

Confirms the model discriminates between lazy and directed prompting before
you build a workshop on the assumption that it does.

---

## The day before

- [ ] `preflight.py` passes on the instance itself
- [ ] `calibrate_model.py` shows a discriminator gap of +40 % or better
- [ ] Elastic IP attached; the URL on your slide resolves from a phone on
      mobile data, not just from your laptop
- [ ] a colleague signs up and submits end to end, from their own device
- [ ] `aws secretsmanager get-secret-value` still works from the instance
- [ ] snapshot the EBS volume after signups so a crash cannot lose accounts
- [ ] check the AI Studio **Spend** page: a runaway loop should be visible
      as spend, and you have a cap set

## If something breaks live

| symptom | first thing to check |
| --- | --- |
| every generation fails | `journalctl -u vibe-challenge -n 50` — usually the key or outbound networking |
| generations hang | your real RPM limit vs `VCC_TARGET_RPM`; lower concurrency |
| someone is stuck at 0 budget | `gateway.grant_budget(db_path, participant_id, 10000)` |
| server is down | `sudo systemctl restart vibe-challenge` — SQLite survives |
| participants can't reach it | security group inbound 8000 from the venue network |
