# Write a function to plot two given values against each other in a bar chart
# the values are the execution time of the create_initial_planning function
# the two values are the execution time of the Java and the execution time of the Python version
# the values are in seconds
from matplotlib import pyplot as plt


def plot_values(java_time, python_time):
    # Create a bar chart with the execution times
    # make the bars different colors
    # show the values on the bars
    plt.bar(["Java", "Python"], [java_time, python_time], color=["red", "blue"])
    # show the values on the bars
    for i, v in enumerate([java_time, python_time]):
        plt.text(i, v, str(v), ha="center", va="bottom")
    plt.title("Execution time of create_initial_planning")
    plt.xlabel("Language")
    plt.ylabel("Time (seconds)")
    plt.show()


plot_values(0.231, 0.199840)
