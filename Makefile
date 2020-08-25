.PHONY: proto image tester

image:
	docker build -t hcloud_python:3.6 .
	
proto:
	python -m grpc_tools.protoc -I src/proto --python_out=./src --grpc_python_out=./src src/proto/container/container.proto
	python -m grpc_tools.protoc -I src/proto --python_out=./src --grpc_python_out=./src src/proto/worker/worker.proto

tester:
	go build -o build/tester test/app.go
