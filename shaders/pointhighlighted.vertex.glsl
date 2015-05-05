precision highp float;

#define W_VAL 1.0
#define Z_VAL 0.1

attribute vec2 curPos;
attribute float pointSize;

varying vec4 vColor;

uniform mat4 mvp;
uniform float fog;
uniform float stroke;
uniform float zoomScalingFactor;
uniform float maxPointSize;

void main(void) {
    if (stroke > 0.0) {
        gl_PointSize = clamp(zoomScalingFactor * pointSize, 17.0, maxPointSize);
    } else {
        gl_PointSize = stroke + clamp(zoomScalingFactor * pointSize, 17.0, maxPointSize);
    }

    vec4 pos = mvp * vec4(curPos.x, 1.0 * curPos.y, Z_VAL, W_VAL);
    gl_Position = pos;

    // Should be orange
    vColor =  vec4(0.89, 0.369, 0.0745, 1.0);
    // vColor = vec4(stroke > 0.0 ? 0.5 * pointColor.xyz : pointColor.xyz, 0.8);
}
