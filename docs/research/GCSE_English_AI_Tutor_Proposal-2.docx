**GCSE English AI Tutor Assistant**

Project Proposal: Deep Agent Architecture with DGX Spark & Reachy Mini

*Supporting Year 10 United Learning Curriculum*

Executive Summary

This proposal outlines the development of an AI-powered tutor assistant
specifically designed to support Year 10 students studying GCSE English
within the United Learning curriculum framework. The system will
leverage cutting-edge hardware (Dell DGX Spark with NVIDIA GB10) and
robotics (Reachy Mini) to create an engaging, personalised learning
experience.

The project combines fine-tuned Large Language Models (LLMs) with an
embodied AI interface to make English learning more interactive and
effective. By fine-tuning models on GCSE-specific content, we can create
a tutor that understands the curriculum requirements, assessment
objectives, and common student challenges.

GCSE English Curriculum Overview

Robert Blake School follows the United Learning curriculum for GCSE
English. The GCSE English programme spans Years 10 and 11, covering both
English Language and English Literature. Here are the key components the
tutor will need to support:

English Literature Components

-   Shakespeare Play: Analysis of language, structure, and dramatic
    techniques

-   19th Century Novel: Close reading and contextual understanding

-   Modern Text/Drama: Works like \'An Inspector Calls\' or \'Blood
    Brothers\'

-   Poetry Anthology: Comparative analysis and unseen poetry

English Language Components

-   Reading: Fiction and non-fiction text analysis

-   Writing: Creative and transactional writing skills

-   Speaking & Listening: Presentation skills (graded separately)

Assessment Objectives

  ----------- -----------------------------------------------------------
  **AO**      **Description**

  AO1         Identify and interpret explicit and implicit information

  AO2         Explain, comment on, and analyse how writers use language
              and structure

  AO3         Compare writers\' ideas and perspectives across texts

  AO4         Evaluate texts critically and support with textual
              references

  AO5         Communicate clearly, effectively, and imaginatively

  AO6         Technical accuracy in spelling, punctuation, and grammar
  ----------- -----------------------------------------------------------

Hardware Architecture

Dell DGX Spark (Pro Max with GB10)

The Dell version of the DGX Spark offers several advantages over the
NVIDIA reference design, including improved thermal management with
front-to-back airflow, a 280W power supply for additional headroom, and
a power LED indicator. Key specifications:

  -------------------------- --------------------------------------------
  **Specification**          **Details**

  Processor                  NVIDIA GB10 Grace Blackwell Superchip
                             (20-core Arm)

  GPU                        Blackwell architecture with 6,144 CUDA cores

  Memory                     128GB unified LPDDR5x (273 GB/s bandwidth)

  AI Performance             Up to 1 petaFLOP at FP4 precision

  Fine-tuning Capacity       Models up to 70B parameters

  Inference Capacity         Models up to 200B parameters

  Networking                 ConnectX-7 with 200Gbps QSFP, 10GbE, Wi-Fi 7

  Operating System           DGX OS (Ubuntu-based)

  Price                      Approximately £3,500-4,000
  -------------------------- --------------------------------------------

Why DGX Spark for This Project

-   128GB unified memory enables fine-tuning Llama 3 8B via LoRA in
    approximately 36 minutes

-   Local processing ensures student data privacy - no cloud dependency

-   Compatible with NVIDIA AI software stack (CUDA, cuDNN, TensorRT,
    PyTorch)

-   Can run DeepSeek R1 distillations, Llama 3, and other open models
    locally

-   Supports Unsloth framework for efficient fine-tuning on consumer
    hardware

Reachy Mini Robot Interface

The Reachy Mini from Pollen Robotics provides an embodied AI interface
that makes learning more engaging. This compact desktop robot serves as
the physical manifestation of the tutor.

  -------------------------- --------------------------------------------
  **Specification**          **Details**

  Dimensions                 28cm height × 16cm width

  Weight                     1.5 kg

  Head Movement              6 degrees of freedom (Stewart platform)

  Body Rotation              360 degrees

  Eyes                       Expressive LED display

  Sensors                    Camera, microphones (4), speakers, IMU

  Compute (Wireless)         Raspberry Pi 4 (onboard)

  SDK                        Python (JavaScript & Scratch coming)

  Price                      From \$299 (Lite) to \$449 (Wireless)
  -------------------------- --------------------------------------------

Benefits for Education

-   Physical presence increases student engagement and attention

-   Expressive movements and eye contact create natural interaction

-   Direct integration with Hugging Face (1.7M+ models, 400K+ datasets)

-   Open-source hardware and software for customisation

-   Can connect to external compute (DGX Spark) via network

Technical Implementation

Model Selection and Fine-Tuning Strategy

For optimal performance on the DGX Spark with educational applications,
we recommend the following model options:

Recommended Base Models

  ------------------ ---------------------- -----------------------------
  **Model**          **Size**               **Use Case**

  Llama 3.3 70B      70B parameters         Best quality, inference only

  Qwen 2.5 32B       32B parameters         Excellent multilingual,
                                            fine-tunable

  Llama 3 8B         8B parameters          Fast fine-tuning (36 mins)

  Mistral 7B         7B parameters          Efficient, proven for
                                            education

  DeepSeek R1        8B parameters          Strong reasoning capabilities
  Distill                                   
  ------------------ ---------------------- -----------------------------

Fine-Tuning Approach: LoRA/QLoRA

Low-Rank Adaptation (LoRA) enables efficient fine-tuning by only
training a small subset of parameters. Combined with 4-bit quantization
(QLoRA), this approach:

-   Reduces memory requirements by \~75% compared to full fine-tuning

-   Produces adapter files of only a few megabytes

-   Preserves base model capabilities while adding domain expertise

-   Enables training on consumer-grade hardware via Unsloth framework

Dataset Creation Strategy

To create an effective GCSE English tutor, we need carefully curated
training data:

Dataset Components

1.  **Curriculum Content: United Learning scheme of work, mark schemes,
    examiner reports**

2.  **Question-Answer Pairs: GCSE-style questions with model answers at
    different grade levels**

3.  **Tutoring Dialogues: Synthetic conversations covering common
    misconceptions**

4.  **Text Analysis Examples: Annotated passages demonstrating analysis
    techniques**

5.  **Feedback Templates: Constructive feedback patterns for different
    skill levels**

Dataset Format

Training data should follow instruction-response format:

\### Instruction:

Explain how Shakespeare uses dramatic irony in Romeo and Juliet Act 3,
Scene 1.

\### Response:

\[Detailed analysis covering AO1, AO2 assessment objectives\...\]

System Architecture

The tutor system connects the DGX Spark (running the fine-tuned LLM)
with the Reachy Mini (providing the physical interface):

Component Communication Flow

Student ↔ Reachy Mini (microphone/camera) ↔ DGX Spark (LLM inference) ↔
Reachy Mini (speaker/movements)

Software Stack

  --------------------- -------------------------------------------------
  **Layer**             **Technologies**

  Operating System      DGX OS (Ubuntu-based) on Spark, Raspberry Pi OS
                        on Reachy

  AI Framework          PyTorch, Hugging Face Transformers, TRL
                        (training)

  Fine-Tuning           Unsloth, PEFT, bitsandbytes (QLoRA)

  Inference             vLLM, TensorRT-LLM, or llama.cpp

  Speech-to-Text        Whisper (local) or faster-whisper

  Text-to-Speech        Coqui TTS or XTTS (local, voice cloning capable)

  Robot SDK             reachy_mini Python SDK

  Orchestration         Custom Python application with async handling
  --------------------- -------------------------------------------------

Key Features to Implement

-   **Adaptive Difficulty: Adjusts explanations based on student
    responses**

-   **Socratic Questioning: Guides discovery rather than giving direct
    answers**

-   **Essay Feedback: Provides constructive criticism aligned to mark
    schemes**

-   **Quote Analysis: Helps break down and analyse textual evidence**

-   **Practice Questions: Generates exam-style questions for revision**

-   **Progress Tracking: Maintains session history and identifies weak
    areas**

-   **Emotional Engagement: Reachy Mini provides encouraging gestures
    and expressions**

Implementation Timeline

  ------------- ------------------ --------------------------------------
  **Phase**     **Duration**       **Activities**

  1\. Setup     2 weeks            Hardware configuration, software
                                   installation, DGX OS setup

  2\. Data Prep 3-4 weeks          Curriculum analysis, dataset creation,
                                   Q&A pair generation

  3\. Fine-Tune 2-3 weeks          LoRA training, evaluation, iteration
                                   on multiple base models

  4\.           2-3 weeks          Speech pipeline, Reachy Mini
  Integration                      connection, orchestration layer

  5\. Testing   2 weeks            User testing with student, feedback
                                   incorporation, refinement

  6\.           1 week             Final configuration, documentation,
  Deployment                       handover
  ------------- ------------------ --------------------------------------

***Total Estimated Duration: 12-15 weeks***

Budget Estimate

  ------------------------------------- ---------------- ----------------
  **Item**                              **Cost (GBP)**   **Notes**

  Dell DGX Spark (Pro Max GB10)         £3,500-4,000     One-time

  Reachy Mini (Wireless version)        £350-400         One-time

  Quality microphone (optional upgrade) £50-100          Optional

  Display/monitor for interaction       £150-300         Optional

  Development time (if outsourced)      Variable         Optional
  ------------------------------------- ---------------- ----------------

**Estimated Hardware Total: £4,000-4,800**

Next Steps

1.  Confirm hardware procurement (Dell DGX Spark, Reachy Mini)

2.  Gather curriculum materials from Robert Blake School / United
    Learning

3.  Begin dataset creation with focus on Year 10 English content

4.  Set up development environment on DGX Spark once received

5.  Experiment with base model selection (Llama 3 8B recommended for
    initial testing)

*This project represents an exciting opportunity to combine cutting-edge
AI hardware with educational best practices, creating a personalised
learning companion that can help your daughter succeed in her GCSE
English studies.*

\-\--

*Document prepared by Claude AI*

*January 2026*
