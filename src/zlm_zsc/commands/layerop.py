from zlm_zsc.base_commands import ZRoutine, ZLayerRoutine


class DeactivateRecord(ZRoutine):

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zdr,
            // Check there is layer first
            [If, [IsEnabled, 359],
            
                [If, [IsDisabled, 351],
                    [ISet, "Tool:Geometry:SDiv", [IGetMax, "Tool:Geometry:SDiv"], 0]
                ]

                // frame current layer if recording
                [If, [IsDisabled, "Tool:Layers:SelectUp"],
                    [ISet, "Tool:Layers:Layers Scrollbar", 0, 256]

                , /* else */
                    [ISet, "Tool:Layers:Layers Scrollbar", 0, 0]
                    [IPress, "Tool:Layers:SelectUp"]
                    [ISet, "Tool:Layers:Layers Scrollbar", 0, [IGetSecondary, "Tool:Layers:Layers Scrollbar"] - 1]
                    [IPress, "Tool:Layers:SelectDown"]
                ]
            ]
        ]
        '''


class SetLayerMode(ZLayerRoutine):

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zslm,
            [ISet, "Tool:Layers:Layers Scrollbar", 0, index]

            [If, mode == 2,
                [ISet, 351, intensity]
            ]

            [VarSet, curMode, [IModGet, 351]]

            [If, curMode != mode,
                [VarSet, wid, [IWidth, 351]]
                [If, mode == 1,
                    [IClick, 351, wid-20, 5]
                ,
                    [If, curMode == 1,
                        [IClick, 351, wid-10, 5]
                    ]
                    [IClick, 351, wid-5, 5]
                ]
            ]
        , index, mode, intensity]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index(),
            layer.mode,
            layer.intensity
        ]


class SetIntensity(ZLayerRoutine):

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zi,
            [ISet, "Tool:Layers:Layers Scrollbar", 0, index]
            [ISet, 351, intensity]
        , index, intensity]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index(),
            layer.intensity
        ]


class ExportLayer(ZLayerRoutine):

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zel,
            [ISet, "Tool:Layers:Layers Scrollbar", 0, index]

            // Activate
            [VarSet, wid, [IWidth, 351]]
            [ISet, 351, 1.0]

            [If, [IModGet, 351] == 0,
                [IClick, 351, wid-5, 5]
            ]

            // save
            [FileNameSetNext, #savePath]
            [IKeyPress, 13, [IPress, TOOL:Export:Export]]

            // Deactivate
            [IClick, 351, wid-5, 5]

        , index, savePath]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]


class CreateLayer(ZLayerRoutine):
    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zcl,
            [VarSet, dllPath, ""]
            [MemReadString, zlmMFileUtilPath, dllPath]

            [IPress, "Tool:Layers:New"]
            [FileExecute, #dllPath, RenameSetNext, #layerName]
            [IPress, "Tool:Layers:Rename"]

        , layerName]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.name
        ]


class RenameLayer(ZLayerRoutine):
    def __init__(self, *args, **kwargs):
        ZLayerRoutine.__init__(self, ('FocusLayer',), *args, **kwargs)

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zrl,
            [VarSet, dllPath, ""]
            [MemReadString, zlmMFileUtilPath, dllPath]

            [RoutineCall, zfl, index]
            [FileExecute, #dllPath, RenameSetNext, #layerName]
            [IPress, "Tool:Layers:Rename"]

        , index, layerName]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index(),
            layer.name
        ]


class FocusLayer(ZLayerRoutine):
    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zfl,
            [ISet, "Tool:Layers:Layers Scrollbar", 0, index]
            [IClick, 351, 5, 5]
        , index]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]


class DeleteLayer(ZLayerRoutine):
    def __init__(self, *args, **kwargs):
        ZLayerRoutine.__init__(self, ('FocusLayer',), *args, **kwargs)

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zdl,
            [RoutineCall, zfl, index]
            [IPress, Tool:Layers:Delete]
        , index]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]


class DuplicateLayer(ZLayerRoutine):
    def __init__(self, *args, **kwargs):
        ZLayerRoutine.__init__(self, ('FocusLayer',), *args, **kwargs)

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zdupl,
            [RoutineCall, zfl, index]
            [IPress, Tool:Layers:Duplicate]
            [IPress, Tool:Layers:SelectDown]

            [VarSet, dllPath, ""]
            [MemReadString, zlmMFileUtilPath, dllPath]

            [FileExecute, #dllPath, RenameSetNext, #name]
            [IPress, "Tool:Layers:Rename"]

            [IF, mvDown,
                [Loop, 1000,
                    [If, [IsEnabled, Tool:Layers:MoveDown],
                        [IPress, Tool:Layers:MoveDown]
                    ,
                        [LoopExit]
                    ]
                ]
            ]
        , index, name, mvDown]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]


class MoveLayer(ZLayerRoutine):
    def __init__(self, *args, **kwargs):
        ZLayerRoutine.__init__(self, ('FocusLayer',), *args, **kwargs)

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zlmv,
            [RoutineCall, zfl, index]

            [VarSet, up, (targetIndex > index)]
            [VarSet, loop, ABS((targetIndex - index))]

            [Loop, #loop,
                [If, up,
                    [IPress, Tool:Layers:MoveUp]
                ,
                    [IPress, Tool:Layers:MoveDown]
                ]
            ]
        , index, targetIndex]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]


class MergeDown(ZLayerRoutine):
    def __init__(self, *args, **kwargs):
        ZLayerRoutine.__init__(self, ('FocusLayer',), *args, **kwargs)

    def definition(self, *args, **kwargs):
        return '''
        [RoutineDef, zlmm,
            [RoutineCall, zfl, index]

            [Loop, count,
                [IPress, Tool:Layers:Merge Down]
            ]
        , index, count]
        '''

    def get_args_from_layer(self, layer):
        return [
            layer.zbrush_index()
        ]
