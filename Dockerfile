FROM python:3.8.0
RUN pip install aiofiles==0.4.0 blinker==1.4 Click==7.0 h11==0.9.0 h2==3.1.0 hpack==3.0.0 Hypercorn==0.7.0 hyperframe==5.2.0 itsdangerous==1.1.0 Jinja2==2.10.1 MarkupSafe==1.1.1 multidict==4.5.2 priority==1.3.0 sortedcontainers==2.1.0 toml==0.10.0 typing-extensions==3.7.4 wheel==0.32.1 wsproto==0.14.1 setuptools==40.4.3 --force-reinstall
RUN pip install flask prometheus_client==0.7.1
COPY script.py /src/
EXPOSE 8080
CMD ["python","/src/script.py","store"]
