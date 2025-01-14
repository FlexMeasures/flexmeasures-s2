FROM lfenergy/flexmeasures

# Install requirements, e.g. like this
#COPY requirements/app.in /app/requirements/flexmeasures_s2.txt
#RUN pip3 install --no-cache-dir -r requirements/flexmeasures_s2.txt

COPY flexmeasures_s2/ /app/flexmeasures_s2
# Make sure FlexMeasures recognizes this plugin (requires FlexMeasures v0.14)
ENV FLEXMEASURES_PLUGINS="/app/flexmeasures_s2"
