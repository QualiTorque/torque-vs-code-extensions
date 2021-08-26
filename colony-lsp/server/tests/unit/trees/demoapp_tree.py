from server.ats.trees.common import PropertyNode, ScalarMappingNode, ScalarMappingsSequence, ScalarNode, TextNode
from server.ats.trees.app import (AmiImageNode, AmiSequenceNode, AppTree, AzureImageNode, AzureSequenceNode,
                                  ConfigurationNode, DockerImageNode, DockerImagesSequence, InfrastructureNode,
                                  InternalPortInfoMappingNode, PortInfoInternalNode,
                                  SourceNode, SpecNode)

tree = AppTree(start_pos=(0, 0), end_pos=(42, 0), errors=[],
               inputs_node=PropertyNode(
                   start_pos=(1, 0), end_pos=(6, 0), errors=[],
                   key=ScalarNode(start_pos=(1, 0), end_pos=(1, 6), errors=[], _text='inputs_node'),
                   value=ScalarMappingsSequence(
                       start_pos=(2, 2), end_pos=(6, 0), errors=[],
                       nodes=[
                           ScalarMappingNode(
                               start_pos=(2, 4), end_pos=(3, 2), errors=[],
                               key=ScalarNode(start_pos=(2, 4), end_pos=(2, 8), errors=[], _text='PORT'),
                               value=ScalarNode(start_pos=(2, 10), end_pos=(2, 14), errors=[], _text='3001')),
                           ScalarMappingNode(
                               start_pos=(3, 4), end_pos=(4, 2), errors=[],
                               key=ScalarNode(start_pos=(3, 4), end_pos=(3, 16), errors=[], _text='INSTANCETYPE'),
                               value=ScalarNode(start_pos=(3, 18), end_pos=(3, 63), errors=[],
                                                _text='t3.small,t3.medium,c5.large,m5.large,m4.large')),
                           ScalarMappingNode(
                               start_pos=(4, 4), end_pos=(5, 2), errors=[],
                               key=ScalarNode(start_pos=(4, 4), end_pos=(4, 17), errors=[], _text='AZURE_VM_SIZE'),
                               value=ScalarNode(start_pos=(4, 19), end_pos=(4, 27), errors=[], _text='Basic_A1')),
                           ScalarMappingNode(
                               start_pos=(5, 4), end_pos=(6, 0), errors=[],
                               key=ScalarNode(start_pos=(5, 4), end_pos=(5, 18), errors=[],
                                              _text='WELCOME_STRING'),
                               value=ScalarNode(start_pos=(5, 20), end_pos=(5, 44), errors=[],
                                                _text='Welcome to Quali Torque!'))])),
               kind=PropertyNode(start_pos=(0, 0), end_pos=(1, 0), errors=[],
                                 key=ScalarNode(start_pos=(0, 0), end_pos=(0, 4), errors=[], _text='kind'),
                                 value=ScalarNode(start_pos=(0, 6), end_pos=(0, 17), errors=[],
                                                  _text='application')),
               spec_version=PropertyNode(start_pos=(41, 0), end_pos=(42, 0), errors=[],
                                         key=ScalarNode(start_pos=(41, 0), end_pos=(41, 12), errors=[],
                                                        _text='spec_version'),
                                         value=ScalarNode(start_pos=(41, 14), end_pos=(41, 15), errors=[],
                                                          _text='1')),
               outputs=None,
               configuration=PropertyNode(
                   start_pos=(18, 0), end_pos=(26, 0), errors=[],
                   key=ScalarNode(start_pos=(18, 0), end_pos=(18, 13), errors=[], _text='configuration'),
                   value=ConfigurationNode(
                       start_pos=(19, 2), end_pos=(26, 0), errors=[],
                       initialization=PropertyNode(
                           start_pos=(21, 2), end_pos=(23, 2), errors=[],
                           key=ScalarNode(start_pos=(21, 2), end_pos=(21, 16), errors=[], _text='initialization'),
                           value=ConfigurationNode.InitializationNode(
                               start_pos=(22, 4), end_pos=(23, 2), errors=[],
                               script=PropertyNode(
                                   start_pos=(22, 4), end_pos=(23, 2), errors=[],
                                   key=ScalarNode(start_pos=(22, 4), end_pos=(22, 10), errors=[], _text='script'),
                                   value=ScalarNode(start_pos=(22, 12), end_pos=(22, 29),
                                                    errors=[], _text='demoapp-server.sh')))),
                       start=PropertyNode(start_pos=(19, 2), end_pos=(21, 2), errors=[],
                                          key=ScalarNode(start_pos=(19, 2), end_pos=(19, 7), errors=[], _text='start'),
                                          value=ConfigurationNode.StartNode(
                                              start_pos=(20, 4), end_pos=(21, 2), errors=[],
                                              script=PropertyNode(
                                                  start_pos=(20, 4), end_pos=(21, 2), errors=[],
                                                  key=ScalarNode(start_pos=(20, 4), end_pos=(20, 10), errors=[],
                                                                 _text='script'),
                                                  value=ScalarNode(start_pos=(20, 12), end_pos=(20, 37), errors=[],
                                                                   _text='demoapp-server-command.sh')),
                                              command=None)),
                       healthcheck=PropertyNode(
                           start_pos=(23, 2), end_pos=(26, 0), errors=[],
                           key=ScalarNode(start_pos=(23, 2), end_pos=(23, 13), errors=[], _text='healthcheck'),
                           value=ConfigurationNode.HealthcheckNode(
                               start_pos=(24, 4), end_pos=(26, 0), errors=[],
                               script=PropertyNode(
                                   start_pos=(25, 4), end_pos=(26, 0), errors=[],
                                   key=ScalarNode(start_pos=(25, 4), end_pos=(25, 10), errors=[], _text='script'),
                                   value=ScalarNode(start_pos=(25, 12), end_pos=(25, 32), errors=[],
                                                    _text='demoapp-server-hc.sh')),
                               timeout=PropertyNode(
                                   start_pos=(24, 4), end_pos=(25, 4), errors=[],
                                   key=ScalarNode(start_pos=(24, 4), end_pos=(24, 11), errors=[], _text='timeout'),
                                   value=ScalarNode(start_pos=(24, 13), end_pos=(24, 17), errors=[], _text='1000')),
                               wait_for_ports=None)))),
               source=PropertyNode(start_pos=(26, 0), end_pos=(41, 0), errors=[],
                                   key=ScalarNode(start_pos=(26, 0), end_pos=(26, 6), errors=[], _text='source'),
                                   value=SourceNode(
                                       start_pos=(27, 2), end_pos=(41, 0), errors=[],
                                       image=PropertyNode(
                                           start_pos=(27, 2), end_pos=(40, 2), errors=[],
                                           key=ScalarNode(start_pos=(27, 2), end_pos=(27, 7),
                                                          errors=[], _text='image'),
                                           value=SourceNode.ImageNode(
                                               start_pos=(28, 4), end_pos=(40, 2), errors=[],
                                               ami=PropertyNode(
                                                   start_pos=(28, 4), end_pos=(35, 4), errors=[],
                                                   key=ScalarNode(
                                                       start_pos=(28, 4), end_pos=(28, 7), errors=[], _text='ami'),
                                                   value=AmiSequenceNode(
                                                       start_pos=(29, 6), end_pos=(35, 4), errors=[],
                                                       nodes=[
                                                           AmiImageNode(
                                                               start_pos=(29, 8), end_pos=(31, 6), errors=[],
                                                               id=PropertyNode(
                                                                   start_pos=(29, 8), end_pos=(30, 8),
                                                                   errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(29, 8), end_pos=(29, 10),
                                                                       errors=[],
                                                                       _text='id'),
                                                                   value=TextNode(
                                                                       start_pos=(29, 12), end_pos=(29, 33),
                                                                       errors=[], _text='ami-0f2ed58082cb08a4d')),
                                                               region=PropertyNode(
                                                                   start_pos=(30, 8), end_pos=(31, 6), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(30, 8), end_pos=(30, 14),
                                                                       errors=[], _text='region'),
                                                                   value=ScalarNode(
                                                                       start_pos=(30, 16), end_pos=(30, 25),
                                                                       errors=[], _text='eu-west-1')),
                                                               username=None),
                                                           AmiImageNode(
                                                               start_pos=(31, 8), end_pos=(33, 6), errors=[],
                                                               id=PropertyNode(
                                                                   start_pos=(31, 8), end_pos=(32, 8), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(31, 8), end_pos=(31, 10),
                                                                       errors=[], _text='id'),
                                                                   value=TextNode(
                                                                       start_pos=(31, 12), end_pos=(31, 33),
                                                                       errors=[], _text='ami-0b1912235a9e70540')),
                                                               region=PropertyNode(
                                                                   start_pos=(32, 8), end_pos=(33, 6), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(32, 8), end_pos=(32, 14),
                                                                       errors=[], _text='region'),
                                                                   value=ScalarNode(
                                                                       start_pos=(32, 16), end_pos=(32, 25),
                                                                       errors=[], _text='eu-west-2')),
                                                               username=None),
                                                           AmiImageNode(
                                                               start_pos=(33, 8), end_pos=(35, 4), errors=[],
                                                               id=PropertyNode(
                                                                   start_pos=(33, 8), end_pos=(34, 8), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(33, 8), end_pos=(33, 10),
                                                                       errors=[], _text='id'),
                                                                   value=TextNode(
                                                                       start_pos=(33, 12), end_pos=(33, 33),
                                                                       errors=[], _text='ami-00e3060e4cb84a493')),
                                                               region=PropertyNode(
                                                                   start_pos=(34, 8), end_pos=(35, 4), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(34, 8), end_pos=(34, 14),
                                                                       errors=[], _text='region'),
                                                                   value=ScalarNode(
                                                                       start_pos=(34, 16), end_pos=(34, 25),
                                                                       errors=[], _text='us-west-1')),
                                                               username=None)])),
                                               azure_image=PropertyNode(
                                                   start_pos=(38, 4), end_pos=(40, 2), errors=[],
                                                   key=ScalarNode(
                                                       start_pos=(38, 4), end_pos=(38, 15), errors=[],
                                                       _text='azure_image'),
                                                   value=AzureSequenceNode(
                                                       start_pos=(39, 6), end_pos=(40, 2), errors=[],
                                                       nodes=[
                                                           AzureImageNode(
                                                               start_pos=(39, 8), end_pos=(40, 2), errors=[],
                                                               urn=PropertyNode(
                                                                   start_pos=(39, 8), end_pos=(40, 2), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(39, 8), end_pos=(39, 11),
                                                                       errors=[], _text='urn'),
                                                                   value=TextNode(
                                                                       start_pos=(39, 13), end_pos=(39, 52),
                                                                       errors=[],
                                                                       _text='Canonical:UbuntuServer:16.04-LTS:latest')),
                                                               username=None, custom_image=None,
                                                               gallery=None, custom=None)])),
                                               docker_image=PropertyNode(
                                                   start_pos=(35, 4), end_pos=(38, 4), errors=[],
                                                   key=ScalarNode(
                                                       start_pos=(35, 4), end_pos=(35, 16), errors=[],
                                                       _text='docker_image'),
                                                   value=DockerImagesSequence(
                                                       start_pos=(36, 6), end_pos=(38, 4), errors=[],
                                                       nodes=[
                                                           DockerImageNode(
                                                               start_pos=(36, 8), end_pos=(38, 4), errors=[],
                                                               name=PropertyNode(
                                                                   start_pos=(37, 8), end_pos=(38, 4), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(37, 8), end_pos=(37, 12),
                                                                       errors=[], _text='name'),
                                                                   value=TextNode(
                                                                       start_pos=(37, 14), end_pos=(37, 24),
                                                                       errors=[], _text='quali/node')),
                                                               pull_secret=None,
                                                               tag=PropertyNode(
                                                                   start_pos=(36, 8), end_pos=(37, 8), errors=[],
                                                                   key=ScalarNode(
                                                                       start_pos=(36, 8), end_pos=(36, 11),
                                                                       errors=[], _text='tag'),
                                                                   value=TextNode(
                                                                       start_pos=(36, 13), end_pos=(36, 24),
                                                                       errors=[], _text='demo_client')),
                                                               username=None)])))),
                                       os_type=PropertyNode(start_pos=(40, 2), end_pos=(41, 0), errors=[],
                                                            key=ScalarNode(
                                                                start_pos=(40, 2), end_pos=(40, 9), errors=[],
                                                                _text='os_type'),
                                                            value=ScalarNode(
                                                                start_pos=(40, 11), end_pos=(40, 16), errors=[],
                                                                _text='linux')))),
               debugging=None,
               infrastructure=PropertyNode(
                   start_pos=(6, 0), end_pos=(18, 0), errors=[],
                   key=ScalarNode(start_pos=(6, 0), end_pos=(6, 14), errors=[], _text='infrastructure'),
                   value=InfrastructureNode(
                       start_pos=(7, 2), end_pos=(18, 0), errors=[],
                       compute=PropertyNode(start_pos=(12, 2), end_pos=(18, 0), errors=[],
                                            key=ScalarNode(
                                                start_pos=(12, 2), end_pos=(12, 9), errors=[], _text='compute'),
                                            value=InfrastructureNode.ComputeNode(
                                                start_pos=(13, 4), end_pos=(18, 0), errors=[],
                                                spec=PropertyNode(
                                                    start_pos=(13, 4), end_pos=(18, 0), errors=[],
                                                    key=ScalarNode(start_pos=(13, 4), end_pos=(13, 8), errors=[],
                                                                   _text='spec'),
                                                    value=SpecNode(
                                                        start_pos=(14, 6), end_pos=(18, 0), errors=[],
                                                        azure=PropertyNode(
                                                            start_pos=(16, 6), end_pos=(18, 0), errors=[],
                                                            key=ScalarNode(
                                                                start_pos=(16, 6), end_pos=(16, 11), errors=[],
                                                                _text='azure'),
                                                            value=SpecNode.AzureSpecNode(
                                                                start_pos=(17, 8), end_pos=(18, 0), errors=[],
                                                                vm_size=PropertyNode(
                                                                    start_pos=(17, 8), end_pos=(18, 0), errors=[],
                                                                    key=ScalarNode(
                                                                        start_pos=(17, 8), end_pos=(17, 15),
                                                                        errors=[], _text='vm_size'),
                                                                    value=TextNode(
                                                                        start_pos=(17, 17), end_pos=(17, 31),
                                                                        errors=[], _text='$AZURE_VM_SIZE')))),
                                                        aws=PropertyNode(
                                                            start_pos=(14, 6), end_pos=(16, 6), errors=[],
                                                            key=ScalarNode(
                                                                start_pos=(14, 6), end_pos=(14, 9), errors=[],
                                                                _text='aws'),
                                                            value=SpecNode.AwsSpecNode(
                                                                start_pos=(15, 8), end_pos=(16, 6), errors=[],
                                                                instance_type=PropertyNode(
                                                                    start_pos=(15, 8), end_pos=(16, 6), errors=[],
                                                                    key=ScalarNode(
                                                                        start_pos=(15, 8), end_pos=(15, 21),
                                                                        errors=[], _text='instance_type'),
                                                                    value=TextNode(
                                                                        start_pos=(15, 23), end_pos=(15, 36),
                                                                        errors=[], _text='$INSTANCETYPE')))),
                                                        kubernetes=None)))),
                       connectivity=PropertyNode(
                           start_pos=(7, 2), end_pos=(12, 2), errors=[],
                           key=ScalarNode(start_pos=(7, 2), end_pos=(7, 14), errors=[], _text='connectivity'),
                           value=InfrastructureNode.ConnectivityNode(
                               start_pos=(8, 4), end_pos=(12, 2), errors=[], external=None,
                               internal=PropertyNode(
                                   start_pos=(8, 4), end_pos=(12, 2), errors=[],
                                   key=ScalarNode(start_pos=(8, 4), end_pos=(8, 12), errors=[], _text='internal'),
                                   value=InfrastructureNode.ConnectivityNode.InternalPortsSequenceNode(
                                       start_pos=(9, 6), end_pos=(12, 2), errors=[],
                                       nodes=[
                                           InternalPortInfoMappingNode(
                                               start_pos=(9, 8), end_pos=(12, 2), errors=[],
                                               key=ScalarNode(start_pos=(9, 8), end_pos=(9, 11),
                                                              errors=[], _text='api'),
                                               value=PortInfoInternalNode(
                                                   start_pos=(10, 10), end_pos=(12, 2), errors=[],
                                                   port=PropertyNode(
                                                       start_pos=(10, 10), end_pos=(11, 10), errors=[],
                                                       key=ScalarNode(
                                                           start_pos=(10, 10), end_pos=(10, 14), errors=[],
                                                           _text='port'),
                                                       value=TextNode(
                                                           start_pos=(10, 16), end_pos=(10, 21), errors=[],
                                                           _text='$PORT')),
                                                   path=PropertyNode(
                                                       start_pos=(11, 10), end_pos=(12, 2), errors=[],
                                                       key=ScalarNode(start_pos=(11, 10), end_pos=(11, 14), errors=[],
                                                                      _text='path'),
                                                       value=TextNode(
                                                           start_pos=(11, 16), end_pos=(11, 18), errors=[], _text='')),
                                                   ingress_healthcheck=None,
                                                   port_range=None))])))),
                       permissions=None)),
               ostype=None)
