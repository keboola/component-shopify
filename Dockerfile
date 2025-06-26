FROM python:3.12-slim
ENV PYTHONIOENCODING=utf-8

# install gcc to be able to build packages - e.g. required by regex, dateparser, also required for pandas
RUN apt-get update && apt-get install -y git

WORKDIR /code/

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install flake8

COPY src/ src
COPY tests/ tests
COPY scripts/ scripts
COPY deploy.sh .
COPY flake8.cfg .

CMD ["python", "-u", "/code/src/component.py"]
