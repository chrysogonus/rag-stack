/*
 * GLSL for the deep field. Colours arrive as uniforms read from the CSS palette and are written out as
 * they are, so the canvas matches the page's sRGB tokens exactly.
 */

/** Point size in pixels for a star of world size `size` at view depth `depth`. */
const POINT_SIZE = /* glsl */ `
uniform float uHalfHeight;
float pointSize(float size, float depth) {
  return size * projectionMatrix[1][1] * uHalfHeight / depth;
}
`

/** A soft disc with a halo; bright stars add the four-point flare of the source catalogue. */
const STAR_SPRITE = /* glsl */ `
float sprite(vec2 p, float spike) {
  float d = length(p);
  float body = smoothstep(0.5, 0.0, d);
  float flare = (exp(-abs(p.x) * 70.0) + exp(-abs(p.y) * 70.0)) * smoothstep(0.5, 0.05, d);
  return body * body * body * 0.9 + exp(-d * d * 40.0) * 0.35 + flare * spike;
}
`

export const starVertex = /* glsl */ `
attribute float aSize;
attribute float aPhase;
attribute float aTint;
uniform float uTime;
uniform float uTravel;
uniform float uDepth;
uniform float uBright;
uniform vec3 uStar;
uniform vec3 uGlint;
uniform vec3 uEmber;
varying vec3 vColor;
varying float vAlpha;
varying float vSpike;
${POINT_SIZE}
void main() {
  float z = mod(position.z + uTravel, uDepth) - uDepth;
  vec4 view = modelViewMatrix * vec4(position.xy, z, 1.0);
  gl_Position = projectionMatrix * view;
  float depth = max(-view.z, 0.001);
  float px = pointSize(aSize, depth);
  gl_PointSize = clamp(px, 1.5, 44.0);
  float twinkle = 0.72 + 0.28 * sin(uTime * (0.4 + aPhase * 1.6) + aPhase * 40.0);
  float fade = smoothstep(uDepth, uDepth * 0.55, depth) * smoothstep(4.0, 40.0, depth);
  vAlpha = fade * twinkle * uBright * clamp(px / 1.5, 0.25, 1.0);
  vSpike = smoothstep(4.0, 5.8, aSize);
  vColor = aTint < 0.78 ? uStar : (aTint < 0.93 ? uGlint : uEmber);
}
`

export const starFragment = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
varying float vSpike;
${STAR_SPRITE}
void main() {
  float a = sprite(gl_PointCoord - 0.5, vSpike) * vAlpha;
  if (a < 0.004) discard;
  gl_FragColor = vec4(vColor, min(a, 1.0));
}
`

/** The same stars as lines: the head where the star is, the tail `uStretch` behind it. Visible only at warp. */
export const streakVertex = /* glsl */ `
attribute float aEnd;
attribute float aTint;
uniform float uTravel;
uniform float uDepth;
uniform float uStretch;
uniform float uStreak;
uniform vec3 uStar;
uniform vec3 uGlint;
uniform vec3 uEmber;
varying vec3 vColor;
varying float vAlpha;
void main() {
  float z = mod(position.z + uTravel, uDepth) - uDepth - aEnd * uStretch;
  vec4 view = modelViewMatrix * vec4(position.xy, z, 1.0);
  gl_Position = projectionMatrix * view;
  float depth = max(-view.z, 0.001);
  float fade = smoothstep(uDepth, uDepth * 0.4, depth) * smoothstep(2.0, 20.0, depth);
  vAlpha = fade * uStreak * (1.0 - aEnd);
  vColor = aTint < 0.78 ? uStar : (aTint < 0.93 ? uGlint : uEmber);
}
`

export const streakFragment = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  if (vAlpha < 0.004) discard;
  gl_FragColor = vec4(vColor, vAlpha);
}
`

export const galaxyVertex = /* glsl */ `
attribute float aSize;
attribute float aReach;
uniform float uTime;
uniform float uBright;
uniform vec3 uStar;
uniform vec3 uGlint;
uniform vec3 uEmber;
varying vec3 vColor;
varying float vAlpha;
varying float vSpike;
${POINT_SIZE}
void main() {
  // Differential rotation: the core turns faster than the rim.
  float turn = uTime * 0.03 / (0.25 + aReach);
  float c = cos(turn), s = sin(turn);
  vec3 p = vec3(c * position.x - s * position.z, position.y, s * position.x + c * position.z);
  vec4 view = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * view;
  float px = pointSize(aSize, max(-view.z, 0.001));
  gl_PointSize = clamp(px, 1.0, 12.0);
  vAlpha = uBright * mix(0.35, 1.0, smoothstep(0.0, 0.25, aReach)) * (1.0 - aReach * 0.55) * clamp(px, 0.35, 1.0);
  vSpike = 0.0;
  vColor = mix(mix(uStar, uEmber, 0.6), uGlint, smoothstep(0.08, 0.6, aReach));
}
`

const NOISE = /* glsl */ `
float hash(vec3 p) {
  p = fract(p * 0.3183099 + 0.1);
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise(vec3 x) {
  vec3 i = floor(x);
  vec3 f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash(i), hash(i + vec3(1, 0, 0)), f.x), mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
    mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x), mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1)), f.x), f.y),
    f.z);
}
float fbm(vec3 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.03 + vec3(1.7, 9.2, 3.1);
    a *= 0.5;
  }
  return v;
}
`

export const nebulaVertex = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

/** Domain-warped clouds, densest along the same tilted band as the 2D sky's dust. */
export const nebulaFragment = /* glsl */ `
uniform float uTime;
uniform float uGlow;
uniform float uOpacity;
uniform vec3 uBand;
uniform vec3 uStar;
uniform vec3 uGlint;
uniform vec3 uEmber;
varying vec3 vDir;
${NOISE}
void main() {
  vec3 d = normalize(vDir);
  float t = uTime * 0.006;
  vec2 q = vec2(fbm(d * 1.8 + t), fbm(d * 1.8 + vec3(5.2, 1.3, 2.8) - t));
  float n = fbm(d * 2.6 + vec3(q, 0.0) * 1.7 + t);
  float band = exp(-pow(dot(d, uBand) / 0.45, 2.0));
  float density = smoothstep(0.4, 0.88, n) * (0.15 + 0.85 * band);
  vec3 colour = mix(uGlint, uEmber, smoothstep(0.5, 0.8, q.x));
  colour = mix(colour, uStar, smoothstep(0.75, 0.95, n) * 0.5);
  gl_FragColor = vec4(colour, clamp(density * uOpacity * uGlow, 0.0, 1.0));
}
`
