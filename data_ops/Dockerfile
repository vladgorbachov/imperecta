# Imperecta data-ops read-path service (Railway deploy)
FROM rust:1-slim AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock* ./
COPY src/ src/
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/imperecta_data_ops /usr/local/bin/data-ops
ENV RUST_LOG=info
EXPOSE 8090
CMD ["data-ops"]
