DEPLOYMENT_ID=cloudburst
#AWS_ID=<YOUR_ACCOUNT_ID_HERE>
AWS_REGION=us-west-2

ECR_REPO_ID=$(DEPLOYMENT_ID)
ECR_REPO_URL=$(AWS_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

build:
	docker compose build $(DEPLOYMENT_ID)

build-nocache:
	docker compose build --no-cache $(DEPLOYMENT_ID)

run: build
	docker compose run --rm --entrypoint bash $(DEPLOYMENT_ID)

test: build
	docker compose up --remove-orphans $(DEPLOYMENT_ID)

terraform-apply:
	cd terraform; terraform init; terraform plan; terraform apply

push: build
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REPO_URL)
	docker tag $(DEPLOYMENT_ID):latest $(ECR_REPO_URL)/$(ECR_REPO_ID):latest
	docker push $(ECR_REPO_URL)/$(ECR_REPO_ID):latest
