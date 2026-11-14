# Dockerfile builds portable system speech archives for Cloud's default catalog.
# The amd64 release builder compiles x64 directly and cross-compiles ARM64, with
# ordinary-language synthesis and MP3 encoding tested before either archive is
# exported. End hosts receive static executables instead of system packages.
FROM debian:bookworm-slim AS builder
# Build static WAV synthesis and a minimal MP3 encoder for old Edge distributions.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake pkg-config curl ca-certificates xz-utils python3 libmp3lame-dev libsonic-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN curl --fail --location --retry 3 https://api.github.com/repos/espeak-ng/espeak-ng/tarball/1.52.0 -o espeak.tar.gz && mkdir espeak && tar xf espeak.tar.gz -C espeak --strip-components=1
RUN cmake -S espeak -B espeak-build -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DCMAKE_EXE_LINKER_FLAGS=-static -DUSE_LIBPCAUDIO=OFF -DUSE_LIBSONIC=OFF -DUSE_MBROLA=OFF -DUSE_ASYNC=OFF -DBUILD_TESTING=OFF && cmake --build espeak-build --target espeak-ng-bin data -j2
RUN curl --fail --location --retry 3 https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz -o ffmpeg.tar.xz && tar xf ffmpeg.tar.xz && cd ffmpeg-7.1.1 && ./configure --prefix=/opt/encoder --disable-everything --disable-autodetect --disable-shared --enable-static --extra-ldflags=-static --pkg-config-flags=--static --disable-x86asm --disable-network --disable-doc --disable-debug --enable-small --disable-programs --enable-ffmpeg --enable-libmp3lame --enable-encoder=libmp3lame --enable-muxer=mp3 --enable-demuxer=wav --enable-decoder=pcm_s16le --enable-filter=aresample,aformat,anull --enable-protocol=file && make -j2 && make install
COPY pack_local_tts.py build_package.py /tools/
ARG RESOURCE_PLATFORM
# Cross compilation avoids host binfmt registration and its privileged setup.
RUN if [ "$RESOURCE_PLATFORM" = linux-arm64 ]; then dpkg --add-architecture arm64 && apt-get update && apt-get install -y --no-install-recommends gcc-aarch64-linux-gnu g++-aarch64-linux-gnu libmp3lame-dev:arm64 libsonic-dev:arm64 qemu-user-static && cmake -S espeak -B arm-build -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++ -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DCMAKE_EXE_LINKER_FLAGS=-static -DUSE_LIBPCAUDIO=OFF -DUSE_LIBSONIC=OFF -DUSE_MBROLA=OFF -DUSE_ASYNC=OFF -DBUILD_TESTING=OFF -DSONIC_LIB=/usr/lib/aarch64-linux-gnu/libsonic.a -DSONIC_INC=/usr/include && cmake --build arm-build --target espeak-ng-bin -j2 && cp arm-build/src/espeak-ng espeak-build/src/espeak-ng && cd ffmpeg-7.1.1 && make distclean && ./configure --prefix=/opt/encoder --enable-cross-compile --arch=aarch64 --target-os=linux --cross-prefix=aarch64-linux-gnu- --disable-everything --disable-autodetect --disable-shared --enable-static --extra-ldflags=-static --disable-network --disable-doc --disable-debug --enable-small --disable-programs --enable-ffmpeg --enable-libmp3lame --enable-encoder=libmp3lame --enable-muxer=mp3 --enable-demuxer=wav --enable-decoder=pcm_s16le --enable-filter=aresample,aformat,anull --enable-protocol=file && make -j2 && make install; fi
RUN python3 /tools/build_package.py "$RESOURCE_PLATFORM"
FROM scratch
COPY --from=builder /out/ /
