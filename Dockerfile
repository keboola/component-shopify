FROM python:3.12-slim
ENV PYTHONIOENCODING=utf-8

# install gcc to be able to build packages - e.g. required by regex, dateparser, also required for pandas
RUN apt-get update && apt-get install -y git

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

COPY flake8.cfg /code/flake8.cfg
RUN pip install flake8

COPY . /code/
WORKDIR /code/

CMD ["python", "-u", "/code/src/component.py"]
