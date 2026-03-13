### Requirement: IMA ADPCM encoder produces compressed output
`shared/adpcm.py` SHALL provide an `encode(pcm_bytes: bytes) -> bytes` function that encodes int16 LE PCM samples to IMA ADPCM, producing approximately 4 bytes of output per 16 bytes of input.

#### Scenario: Encode reduces frame size by ~4x
- **WHEN** `encode()` is called with 640 bytes of int16 LE PCM (320 samples)
- **THEN** the output SHALL be 164 bytes or fewer (4-byte state header + 160 bytes of nibbles)

#### Scenario: Encode handles empty input
- **WHEN** `encode()` is called with an empty bytes object
- **THEN** it SHALL return an empty bytes object without raising

### Requirement: IMA ADPCM decoder reconstructs PCM
`shared/adpcm.py` SHALL provide a `decode(adpcm_bytes: bytes) -> bytes` function that decodes IMA ADPCM bytes back to int16 LE PCM samples.

#### Scenario: Encode–decode round-trip preserves signal shape
- **WHEN** a PCM buffer is encoded then decoded
- **THEN** the decoded PCM SHALL have the same length as the original
- **THEN** the RMS difference between original and decoded samples SHALL be less than 5% of the original RMS (acceptable quantisation noise)

#### Scenario: Decode handles empty input
- **WHEN** `decode()` is called with an empty bytes object
- **THEN** it SHALL return an empty bytes object without raising

### Requirement: ADPCM codec tag constants are defined
`shared/adpcm.py` SHALL export integer constants `CODEC_RAW = 0` and `CODEC_ADPCM = 1` for use in frame headers.

#### Scenario: Constants are importable
- **WHEN** `from shared.adpcm import CODEC_RAW, CODEC_ADPCM` is executed
- **THEN** `CODEC_RAW` SHALL equal `0` and `CODEC_ADPCM` SHALL equal `1`
