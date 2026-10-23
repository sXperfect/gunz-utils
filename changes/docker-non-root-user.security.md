The container image now declares its runtime user explicitly (`USER $MAMBA_USER`)
so the image never depends on the base image default, and gunz-style reports no
violation for the Dockerfile.
