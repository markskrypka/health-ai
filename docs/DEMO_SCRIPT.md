# Clínica Arenal — 10-Minute Jury Demo Script

---

## 👥 Team Roles

* **Presenter (Speaker):** Hooks the jury, introduces each test scenario, and explains the clinical/technical decisions.
* **Patient (Actor):** Speaks naturally on the phone/simulator with realistic pauses and conversational quirks.
* **Operator (Screen / Tech):** Projects the Live Dashboard, triggers the simulator, and highlights real-time events.

---

## ⏱️ Timeline & Presentation Flow

```
[00:00 - 01:30]  The Pitch: Why Voice AI in Healthcare Fails (and How We Fixed It)
[01:30 - 04:00]  Live Call #1: Natural Scheduling, Mid-Call Change of Mind & Insurance
[04:00 - 06:15]  Live Call #2: Clinical Intelligence & Doctor Name Disambiguation
[06:15 - 08:00]  Live Call #3: The "WOW" Safety Barrier — Red Flag Triage & 112 Escalation
[08:00 - 09:15]  Behind the Curtain: Live Audit Trail, 8 kHz Pipeline & 172/172 Points
[09:15 - 10:00]  Closing & Jury Q&A
```

---

## 🎬 Section 1: The Hook (00:00 – 01:30)

**Presenter:**
> *"Good morning, members of the jury. Voice AI in healthcare usually fails where it matters most: it talks over patients, mishears names, gets confused by insurance restrictions, and worse—hallucinates medical advice.*
>
> *We built an autonomous clinic receptionist for Clínica Arenal that achieves **172 out of 172 points on the benchmark**. It combines sub-second response times, zero hallucinations, strict atomic write guarantees at hang-up, and clinical-grade patient triage.*
>
> *Today, we’re not showing you a canned video. We’re calling our agent live right now."*

---

## 📞 Live Call #1: Conversational Booking & Changing Mind (01:30 – 04:00)

**Presenter:**
> *"Watch how the agent handles a conversational booking with an immediate change of mind and insurance routing."*

### Spoken Dialogue (English or Spanish)

* **Agent:** *"Clínica Arenal, good morning. How can I help you?"*
* **Patient:** *"Hi, good morning. I need to book the earliest GP appointment available. My name is Josefa Domínguez Navarro."*
* **Agent:** *(Runs lookup seamlessly, uses holding phrase if needed)*  
  *"One moment, please... Josefa, the earliest slot with Dr. Martín Sáez at Arenal Sur is Monday, September 21st at 9:00 AM. Does that work for you?"*
* **Patient (Change of mind mid-flight):** *"Actually, 9:00 AM is too early. Do you have anything in the afternoon? And by the way, I'm with Mapfre."*
* **Agent:** *"Checking afternoon slots for Mapfre... I can offer you Monday, September 21st at 4:30 PM with Dr. Sáez at Arenal Sur. Shall I book that for you?"*
* **Patient:** *"Yes, perfect. Please book it."*
* **Agent:** *"Your appointment is confirmed for Monday, September 21st at 4:30 PM with Dr. Sáez at Arenal Sur. Thank you for calling Clínica Arenal, have a great day!"*

**Presenter (Pointing at Screen):**
> *"Notice three critical things on the dashboard:*
> 1. *When the patient changed their mind, the agent didn't double-book. It atomically replaced the morning offer with the afternoon slot.*
> 2. *The insurance (Mapfre) was verified against the doctor’s coverage in real time.*
> 3. *The transaction was finalized strictly when the receiver hung up."*

---

## 📞 Live Call #2: Doctor Disambiguation & Near-Miss Names (04:00 – 06:15)

**Presenter:**
> *"In a busy clinic, patients often say: 'Give me an appointment with Dr. Iglesias'. But Clínica Arenal has Dr. Iglesias in Dermatology and Dr. Iglesia in Orthopaedics. Traditional bots pick the wrong doctor. Watch how ours handles ambiguity."*

### Spoken Dialogue

* **Agent:** *"Clínica Arenal, good morning. How can I help you?"*
* **Patient:** *"Hello, I'd like to book an appointment with doctor Iglesias as soon as possible."*
* **Agent:** *"We have two doctors with similar names: Dr. Carmen Iglesias in Dermatology and Dr. Marcos Iglesia in Orthopaedics. Which specialty or doctor are you looking for?"*
* **Patient:** *"Oh, Dermatology for a skin checkup, please."*
* **Agent:** *"Got it, Dr. Carmen Iglesias in Dermatology. Could you give me your full name, please?"*
* **Patient:** *"Carlos Mendoza Ruiz."*
* **Agent:** *(Checks patient and finds slots)*  
  *"Carlos, the first available Dermatology consultation is Wednesday, September 23rd at 11:15 AM at Arenal Centro. Would you like me to book it?"*
* **Patient:** *"Yes, that’s great. Thank you!"*
* **Agent:** *"Booked for Wednesday at 11:15 AM with Dr. Carmen Iglesias at Arenal Centro. Have a good day!"*

**Presenter:**
> *"Zero guesswork. It disambiguated the phonetic collision proactively before hitting the booking engine."*

---

## 🚨 Live Call #3: The "WOW" Factor — Clinical Red Flags & 112 Triage (06:15 – 08:00)

**Presenter:**
> *"Now the ultimate test: What happens when an emergency strikes? Many AI bots try to schedule an appointment for next week. That can cost a life. Watch our clinical safety guardrails."*

### Spoken Dialogue

* **Agent:** *"Clínica Arenal, good morning. How can I help you?"*
* **Patient (distressed voice):** *"Hi... I was hoping to see a doctor today. I have intense chest tightness and I'm having trouble breathing..."*
* **Agent:** *(Halts all booking workflows immediately)*  
  *"Please hang up and dial 112 immediately. Severe chest tightness and difficulty breathing require immediate emergency medical care. Do not wait for a clinic appointment—call 112 now."*
* **Patient:** *"Okay, calling 112 now."*

**Presenter (Highlighting Dashboard):**
> *"Look at the control room:*
> * *The agent **refused to book a slot**.*
> * *An `ESCALATE(medical_emergency)` event was latched in the audit log.*
> * *Even if the caller had asked for a doctor afterwards, the system is hard-locked against booking non-emergency appointments during a red-flag event. This is clinical safety by design."*

---

## 💻 Section 4: Under the Hood & Live Audit (08:00 – 09:15)

**Presenter (Operator shows the console timeline):**
> *"What you see here is why we scored **172/172 points**:*
> 1. ***Ultra-low latency:*** *Powered by Gemini Flash + Deepgram/ElevenLabs, averaging under 1.5s per turn over raw 8 kHz telephony frames.*
> 2. ***LookupMute:*** *The microphone is temporarily deafened during API queries so background coughing or 'uh-huh, I’m waiting' never aborts an in-flight search.*
> 3. ***Complete Post-Call Observability:*** *Every turn, phonetic DNI verification, insurer check, and API response is logged in an append-only audit trail for medical compliance."*

---

## 🎯 Section 5: Closing (09:15 – 10:00)

**Presenter:**
> *"Clínica Arenal handles 80% of routine inbound administrative calls without adding reception overhead, while protecting patient health with zero tolerance for hallucinations or misdirection.*
>
> *Thank you very much. We’d love to take your questions or even have one of the judges dial into the system right now!"*

---

## 💡 Quick Tips for the Live Room

1. **Audio Backup:** Have a phone connected to `/phone` or a wired mic; don't rely on laptop room mics in noisy auditoriums.
2. **Network Backup:** Have a mobile hotspot ready in case the venue's WiFi drops.
3. **Practice Once:** Do one 3-minute dry run of the 3 calls with your team before heading to the stage.
