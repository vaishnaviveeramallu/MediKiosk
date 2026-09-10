/**
 * Lightweight client-side WAV audio recorder for MediKiosk.
 * Captures microphone audio using the Web Audio API (AudioContext)
 * and encodes it directly into a standard 16kHz mono 16-bit PCM WAV Blob.
 */

export class WavAudioRecorder {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private audioBuffers: Float32Array[] = [];
  private recordingLength = 0;
  private _isRecording = false;

  public get isRecording(): boolean {
    return this._isRecording;
  }

  /**
   * Request microphone permission and start recording audio.
   */
  public async start(): Promise<void> {
    if (this._isRecording) return;

    this.audioBuffers = [];
    this.recordingLength = 0;

    // 1. Request microphone access
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    // 2. Initialize AudioContext at target 16000 Hz if supported, or native
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    this.audioContext = new AudioCtx();

    // 3. Connect audio nodes
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Buffer size 4096, 1 input channel, 1 output channel
    this.scriptProcessor = this.audioContext.createScriptProcessor(4096, 1, 1);

    this.scriptProcessor.onaudioprocess = (event: AudioProcessingEvent) => {
      if (!this._isRecording) return;
      const channelData = event.inputBuffer.getChannelData(0);
      // Clone the slice
      this.audioBuffers.push(new Float32Array(channelData));
      this.recordingLength += channelData.length;
    };

    this.sourceNode.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.audioContext.destination);

    this._isRecording = true;
  }

  /**
   * Stop recording and return standard 16kHz mono WAV Blob.
   */
  public async stop(): Promise<Blob> {
    this._isRecording = false;

    // Disconnect and release microphone
    if (this.sourceNode && this.scriptProcessor) {
      try {
        this.sourceNode.disconnect();
        this.scriptProcessor.disconnect();
      } catch (_) {}
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    const sourceSampleRate = this.audioContext ? this.audioContext.sampleRate : 44100;
    if (this.audioContext && this.audioContext.state !== "closed") {
      try {
        await this.audioContext.close();
      } catch (_) {}
    }

    // Merge buffers
    const merged = new Float32Array(this.recordingLength);
    let offset = 0;
    for (const buf of this.audioBuffers) {
      merged.set(buf, offset);
      offset += buf.length;
    }

    // Downsample to 16000 Hz if needed
    const targetSampleRate = 16000;
    const downsampled = this.downsampleBuffer(merged, sourceSampleRate, targetSampleRate);

    // Encode standard 16-bit PCM WAV
    const wavBlob = this.encodeWav(downsampled, targetSampleRate);
    this.audioBuffers = [];
    this.recordingLength = 0;

    return wavBlob;
  }

  /**
   * Cancel and cleanup recording without returning a Blob.
   */
  public cancel(): void {
    this._isRecording = false;
    if (this.sourceNode && this.scriptProcessor) {
      try {
        this.sourceNode.disconnect();
        this.scriptProcessor.disconnect();
      } catch (_) {}
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      try {
        this.audioContext.close();
      } catch (_) {}
    }
    this.audioBuffers = [];
    this.recordingLength = 0;
  }

  /**
   * Downsample audio buffer to 16000 Hz.
   */
  private downsampleBuffer(
    buffer: Float32Array,
    inputRate: number,
    outputRate: number
  ): Float32Array {
    if (inputRate === outputRate) {
      return buffer;
    }
    const sampleRateRatio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / sampleRateRatio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;

    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  /**
   * Build 44-byte RIFF WAV header and write 16-bit linear PCM samples.
   */
  private encodeWav(samples: Float32Array, sampleRate: number): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    // 1. "RIFF" identifier
    this.writeString(view, 0, "RIFF");
    // File length minus 8
    view.setUint32(4, 36 + samples.length * 2, true);
    // "WAVE"
    this.writeString(view, 8, "WAVE");

    // 2. "fmt " sub-chunk
    this.writeString(view, 12, "fmt ");
    // Subchunk1Size (16 for PCM)
    view.setUint32(16, 16, true);
    // AudioFormat (1 = PCM)
    view.setUint16(20, 1, true);
    // NumChannels (1 = Mono)
    view.setUint16(22, 1, true);
    // SampleRate (16000)
    view.setUint32(24, sampleRate, true);
    // ByteRate (SampleRate * NumChannels * BitsPerSample/8 = 16000 * 1 * 2 = 32000)
    view.setUint32(28, sampleRate * 2, true);
    // BlockAlign (NumChannels * BitsPerSample/8 = 2)
    view.setUint16(32, 2, true);
    // BitsPerSample (16 bits)
    view.setUint16(34, 16, true);

    // 3. "data" sub-chunk
    this.writeString(view, 36, "data");
    // Subchunk2Size (NumSamples * NumChannels * BitsPerSample/8)
    view.setUint32(40, samples.length * 2, true);

    // 4. Write 16-bit PCM samples (clamp float between -1.0 and 1.0)
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      // Convert float to 16-bit signed integer
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([buffer], { type: "audio/wav" });
  }

  private writeString(view: DataView, offset: number, string: string): void {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }
}
