FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY pyproject.toml .
RUN pip install uv && uv pip install --system .

COPY . .

CMD ["lambda_handler.handler"]
