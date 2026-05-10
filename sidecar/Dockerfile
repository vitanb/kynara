FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/sidecar .

FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/sidecar /sidecar
EXPOSE 7070
USER nonroot:nonroot
ENTRYPOINT ["/sidecar"]
