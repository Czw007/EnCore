# EnCore
EnCore: Exploiting System Environment and Correlation Information for Misconfiguration Detection

As software systems become more complex and configurable,
failures due to misconfigurations are becoming a critical
problem. Such failures often have serious functionality,
security and financial consequences. Further, diagnosis and
remediation for such failures require reasoning across the
software stack and its operating environment, making it difficult
and costly.
We present a framework and tool called EnCore to automatically
detect software misconfigurations. EnCore takes
into account two important factors that are unexploited before:
the interaction between the configuration settings and
the executing environment, as well as the rich correlations
between configuration entries. We embrace the emerging
trend of viewing systems as data, and exploit this to extract
information about the execution environment in which
a configuration setting is used. EnCore learns configuration
rules from a given set of sample configurations. With training
data enriched with the execution context of configurations,
EnCore is able to learn a broad set of configuration
anomalies that spans the entire system. EnCore is effective
in detecting both injected errors and known real-world problems
– it finds 37 new misconfigurations in Amazon EC2
public images and 24 new configuration problems in a commercial
private cloud. By systematically exploiting environment
information and by learning correlation rules across
multiple configuration settings, EnCore detects 1.6x to 3.5x
more misconfiguration anomalies than previous approaches.
